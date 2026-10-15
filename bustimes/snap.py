"""Propose RouteLinks for a service by map matching a vehicle journey's location history.

The journey can come from a remote site (e.g. bustimes.org, handy for development),
while the service and stops are local
"""

import math
from dataclasses import dataclass
from datetime import datetime
from itertools import pairwise
from urllib.parse import urlparse

import polyline
import requests
from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.geos import LineString as GEOSLineString
from shapely import wkt
from shapely.geometry import LineString, Point
from shapely.ops import substring

from busstops.models import StopPoint
from vehicles.time_aware_polyline import decode_time_aware_polyline

from .models import RouteLink

MAP_MATCH_URL = "https://api.stadiamaps.com/map_match/v1"
ROUTE_URL = "https://api.stadiamaps.com/route/v1"
CHUNK_METRES = 100_000  # Valhalla won't match traces longer than 200km
STOP_TOLERANCE_METRES = 60
FALLBACK_TOLERANCE_METRES = 500  # e.g. bus stations off the road network


def haversine(a, b):
    lon1, lat1, lon2, lat2 = map(math.radians, (*a[:2], *b[:2]))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 12_742_000 * math.asin(math.sqrt(h))


def to_metres(geometry):
    geometry = geometry.transform(27700, clone=True)
    return wkt.loads(geometry.wkt)


def to_degrees(geometry):
    geometry = GEOSGeometry(geometry.wkt, srid=27700)
    geometry.transform(4326)
    return geometry


def locate(shape, point, start, tolerance=STOP_TOLERANCE_METRES):
    """(distance along shape, distance from shape) of the first close approach to point
    after start"""
    along = 0
    best = None
    for (x1, y1), (x2, y2) in pairwise(shape.coords):
        length = math.hypot(x2 - x1, y2 - y1)
        if along + length >= start and length:
            t = ((point.x - x1) * (x2 - x1) + (point.y - y1) * (y2 - y1)) / length**2
            t = min(max(t, 0, (start - along) / length), 1)
            offset = math.hypot(
                x1 + t * (x2 - x1) - point.x, y1 + t * (y2 - y1) - point.y
            )
            if offset <= tolerance:
                if best is None or offset < best[1]:
                    best = (along + t * length, offset)
            elif best is not None:
                break  # moved away again - stick with the first pass
        along += length
    return best


def get_journey(journey, remote="https://bustimes.org"):
    if "/" in journey:
        url = urlparse(journey)
        remote = f"{url.scheme}://{url.netloc}"
        journey = url.path.rstrip("/").split("/")[-1]
    response = requests.get(
        f"{remote}/api/vehiclejourneys/{journey}/details.json", timeout=30
    )
    response.raise_for_status()
    return response.json()


def get_points(journey):
    first = journey["trip"]["times"][0]
    start = first.get("actual_departure_time") or first["aimed_departure_time"]
    start = datetime.fromisoformat(start).timestamp() - 300
    return [
        point
        for point in decode_time_aware_polyline(journey["time_aware_polyline"])
        if point[2] >= start
    ]


def decode_legs(trip):
    return [
        (lon, lat)
        for leg in trip["legs"]
        for lat, lon in polyline.decode(leg["shape"], precision=6)
    ]


def map_match(points):
    chunks = [[points[0]]]
    distance = 0
    for a, b in pairwise(points):
        distance += haversine(a, b)
        if distance > CHUNK_METRES:
            chunks.append([a])  # overlap by one point
            distance = 0
        chunks[-1].append(b)

    session = requests.Session()
    session.params.update({"api_key": settings.STADIA_MAPS_API_KEY})

    # Valhalla breaks the trace where points are far apart (>2km),
    # returning the subsequent pieces as "alternates"
    pieces = []
    errors = []
    for chunk in chunks:
        response = session.post(
            MAP_MATCH_URL,
            json={
                "costing": "bus",
                "shape_match": "map_snap",
                "trace_options": {"gps_accuracy": 50, "search_radius": 100},
                "shape": [
                    {"lon": lon, "lat": lat, "time": time} for lon, lat, time in chunk
                ],
            },
            timeout=60,
        ).json()
        if "trip" not in response:
            errors.append(response)
            continue
        pieces.append(decode_legs(response["trip"]))
        pieces += [
            decode_legs(alternate["trip"])
            for alternate in response.get("alternates", ())
        ]

    coords = []
    for piece in pieces:
        if coords and haversine(coords[-1], piece[0]) > 20:
            response = session.post(
                ROUTE_URL,
                json={
                    "costing": "bus",
                    "locations": [
                        {"lon": coords[-1][0], "lat": coords[-1][1]},
                        {"lon": piece[0][0], "lat": piece[0][1]},
                    ],
                },
                timeout=60,
            ).json()
            if "trip" in response:
                piece = decode_legs(response["trip"]) + piece
            else:
                errors.append(response)
        for coord in piece:
            if not coords or coords[-1] != coord:
                coords.append(coord)
    return coords, errors


@dataclass
class Proposal:
    from_stop: StopPoint
    to_stop: StopPoint
    geometry: GEOSGeometry
    length: float
    detour: float  # length / straight line distance
    offset: float  # furthest either stop is from the matched route
    existing: RouteLink | None
    difference: float | None  # Hausdorff distance from existing geometry

    @property
    def warnings(self):
        warnings = []
        if self.detour > 1.6:
            warnings.append(f"{self.detour:.1f}× straight line")
        if self.offset > 30:
            warnings.append(f"stop {self.offset:.0f}m from route")
        if self.existing and self.existing.override:
            warnings.append("existing link is an override")
        return warnings

    @property
    def checked(self):
        return not self.warnings and (self.difference is None or self.difference > 10)


def propose(journey, service, coords):
    """match each consecutive pair of the journey's stops to a substring of the matched
    route"""
    shape = to_metres(GEOSLineString(coords, srid=4326))

    atco_codes = [time["stop"]["atco_code"] for time in journey["trip"]["times"]]
    stops = StopPoint.objects.filter(
        atco_code__in=atco_codes, latlong__isnull=False
    ).in_bulk()
    existing = {
        (link.from_stop_id, link.to_stop_id): link
        for link in RouteLink.objects.filter(
            service=service, from_stop__in=stops, to_stop__in=stops
        )
    }

    proposals = []
    problems = []
    position = 0
    previous = None  # (stop, point, distance along shape, offset)
    for atco_code in atco_codes:
        stop = stops.get(atco_code)
        if not stop:
            problems.append(f"no local stop {atco_code}")
            previous = None
            continue
        point = Point(to_metres(stop.latlong).coords[0])
        located = locate(shape, point, position) or locate(
            shape, point, position, FALLBACK_TOLERANCE_METRES
        )
        if located is None:
            problems.append(f"{stop} ({atco_code}) not near the matched route")
            previous = None
            continue
        distance, offset = located
        position = distance

        if previous and distance > previous[2]:
            line = substring(shape, previous[2], distance)
            if line.geom_type == "LineString":
                # straight connectors to stops that aren't on the matched route
                coords = list(line.coords)
                if previous[3] > 30:
                    coords.insert(0, previous[1].coords[0])
                if offset > 30:
                    coords.append(point.coords[0])
                line = LineString(coords)
                link = existing.get((previous[0].atco_code, atco_code))
                proposals.append(
                    Proposal(
                        from_stop=previous[0],
                        to_stop=stop,
                        geometry=to_degrees(line),
                        length=line.length,
                        detour=line.length / max(previous[1].distance(point), 1),
                        offset=max(offset, previous[3]),
                        existing=link,
                        difference=link
                        and to_metres(link.geometry).hausdorff_distance(line),
                    )
                )
        previous = (stop, point, distance, offset)

    return proposals, problems

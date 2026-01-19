import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from itertools import pairwise

import pandas as pd
import gtfs_kit
import shapely.ops as so
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Min
from django.utils.dateparse import parse_duration

from busstops.models import DataSource, Operator, Service, StopPoint

from ...download_utils import download_if_modified
from ...models import Route, StopTime, Trip, RouteLink
from ...gtfs_utils import get_calendars, MODES

logger = logging.getLogger(__name__)


MODES = {**MODES, 3: "coach"}


def get_stoppoint(stop, source):
    stoppoint = StopPoint(
        atco_code=stop.stop_id,
        naptan_code=stop.stop_code,
        common_name=stop.stop_name,
        active=True,
        source=source,
        latlong=f"POINT({stop.stop_lon} {stop.stop_lat})",
    )

    if len(stoppoint.common_name) > 48:
        if " (" in stoppoint.common_name and stoppoint.common_name[-1] == ")":
            stoppoint.common_name, stoppoint.indicator = stoppoint.common_name.split(
                " (", 1
            )
            stoppoint.indicator = stoppoint.indicator[:-1]
        else:
            stoppoint.common_name = stoppoint.common_name[:48]

    return stoppoint


class Command(BaseCommand):
    def handle(self, *args, **options):
        operator = Operator.objects.get(name="FlixBus")
        source, _ = DataSource.objects.get_or_create(name="FlixBus")

        path = settings.DATA_DIR / Path("flixbus_eu.zip")

        source.url = "https://gtfs.gis.flix.tech/gtfs_generic_eu.zip"

        modified, last_modified = download_if_modified(path, source)

        if not modified:
            return

        logger.info(f"{source} {last_modified}")

        feed = gtfs_kit.read_feed(path, dist_units="km")

        mask = feed.routes.route_id.str.startswith(
            "UK"
        ) | feed.routes.route_long_name.str.contains("London")
        feed = feed.restrict_to_routes(feed.routes[mask].route_id)

        stops_data = {row.stop_id: row for row in feed.stops.itertuples()}
        stop_codes = {
            stop_code.code: stop_code.stop_id for stop_code in source.stopcode_set.all()
        }
        missing_stops = {}

        existing_services = {
            service.line_name: service for service in operator.service_set.all()
        }
        existing_routes = {route.code: route for route in source.route_set.all()}
        routes = []

        calendars = get_calendars(feed, source)

        # get UTC offset (0 or 1 hours) at midday at the start of each calendar
        # (the data uses UTC times but we want local times)
        tzinfo = ZoneInfo("Europe/London")
        utc_offsets = {
            calendar.start_date: datetime.strptime(
                f"{calendar.start_date} 12", "%Y%m%d %H"
            )
            .replace(tzinfo=tzinfo)
            .utcoffset()
            for calendar in calendars.values()
        }

        geometries = {}
        for row in feed.get_routes(as_gdf=True).itertuples():
            if row.geometry:
                geometries[row.route_id] = row.geometry.wkt
            else:
                logger.info(row)

        for row in feed.routes.itertuples():
            line_name = row.route_id

            if line_name in existing_services:
                service = existing_services[line_name]
            elif line_name.removeprefix("UK") in existing_services:
                service = existing_services[line_name.removeprefix("UK")]
            else:
                service = Service()

            if row.route_id in existing_routes:
                route = existing_routes[row.route_id]
            else:
                route = Route(code=row.route_id, source=source)
            route.service = service
            route.line_name = line_name
            service.line_name = line_name
            service.description = route.description = row.route_long_name
            service.current = True
            service.colour_id = operator.colour_id
            service.source = source
            service.geometry = geometries.get(row.route_id)
            service.region_id = "GB"
            service.mode = MODES[row.route_type]

            service.save()
            service.operator.add(operator)
            route.save()

            routes.append(route)

            existing_routes[route.code] = route  # deals with duplicate rows

        existing_trips = {
            trip.vehicle_journey_code: trip for trip in operator.trip_set.all()
        }
        trips = {}
        for row in feed.trips.itertuples():
            # evenness of the number after the first hyphen
            # (e.g. "3" in "UK070-3-1910012026-...")
            # determines direction
            journey_number = int(row.trip_id.split("-")[1])
            trip = Trip(
                route=existing_routes[row.route_id],
                calendar=calendars[row.service_id],
                inbound=journey_number % 2 == 0,
                vehicle_journey_code=row.trip_id,
                headsign=row.trip_headsign if pd.notna(row.trip_headsign) else None,
                operator=operator,
                journey_pattern=row.shape_id,
            )
            if trip.vehicle_journey_code in existing_trips:
                # reuse existing trip id
                trip.id = existing_trips[trip.vehicle_journey_code].id
            trips[trip.vehicle_journey_code] = trip
        del existing_trips

        stop_times = []
        for trip_id, group in pd.merge(
            feed.stop_times, feed.trips, on="trip_id"
        ).groupby("trip_id"):
            trip = trips[trip_id]
            offset = utc_offsets[trip.calendar.start_date]

            stop_time = None

            for row in group.sort_values("stop_sequence").itertuples():
                arrival_time = parse_duration(row.arrival_time) + offset
                departure_time = parse_duration(row.departure_time) + offset

                stop_time = StopTime(
                    arrival=arrival_time,
                    departure=departure_time,
                    sequence=row.stop_sequence,
                    trip=trip,
                    pick_up=(row.pickup_type != 1),
                    set_down=(row.drop_off_type != 1),
                )

                if trip.start is None:
                    # first stop in trip
                    trip.start = stop_time.departure
                    stop_time.set_down = False

                # (a bit pointless as I think all their stops are timing points and/or they leave this column blank)
                if pd.notna(row.timepoint) and row.timepoint == 1:
                    stop_time.timing_status = "PTP"
                else:
                    stop_time.timing_status = "OTH"

                if row.stop_id in stop_codes:
                    stop_time.stop_id = stop_codes[row.stop_id]
                else:
                    stop = stops_data[row.stop_id]
                    stop_time.stop_id = row.stop_id

                    # create new StopPoint
                    if row.stop_id not in missing_stops:
                        missing_stops[row.stop_id] = get_stoppoint(stop, source)

                        logger.info(
                            f"{stop.stop_name} {stop.stop_code} {stop.stop_timezone} {stop.platform_code}"
                        )
                        logger.info(
                            f"https://bustimes.org/map#16/{stop.stop_lat}/{stop.stop_lon}"
                        )
                        logger.info(
                            f"https://bustimes.org/admin/busstops/stopcode/add/?code={row.stop_id}\n"
                        )

                stop_times.append(stop_time)

            # last stop in trip
            trip.end = stop_time.arrival
            stop_time.pick_up = False
            trip.destination_id = stop_time.stop_id

        StopPoint.objects.bulk_create(
            missing_stops.values(),
            update_conflicts=True,
            update_fields=["common_name", "indicator", "naptan_code", "latlong"],
            unique_fields=["atco_code"],
        )

        # if no timing points specified (because FlixBus), set all stops as timing points
        if all(stop_time.timing_status == "OTH" for stop_time in stop_times):
            for stop_time in stop_times:
                stop_time.timing_status = "PTP"

        with transaction.atomic():
            Trip.objects.bulk_create([trip for trip in trips.values() if not trip.id])
            existing_trips = [trip for trip in trips.values() if trip.id]
            Trip.objects.bulk_update(
                existing_trips,
                fields=[
                    "route",
                    "calendar",
                    "inbound",
                    "start",
                    "end",
                    "destination",
                    "vehicle_journey_code",
                    "headsign",
                ],
            )

            StopTime.objects.filter(trip__in=existing_trips).delete()
            StopTime.objects.bulk_create(stop_times)

            for service in source.service_set.filter(current=True):
                service.do_stop_usages()
                service.update_search_vector()

            logger.info(
                source.route_set.exclude(id__in=[route.id for route in routes]).delete()
            )

            for route in source.route_set.annotate(
                start=Min("trip__calendar__start_date")
            ):
                route.start_date = route.start
                route.save(update_fields=["start_date"])

            logger.info(
                operator.trip_set.exclude(
                    id__in=[trip.id for trip in trips.values()]
                ).delete()
            )
            logger.info(
                operator.service_set.filter(current=True, route__isnull=True).update(
                    current=False
                )
            )
            if last_modified:
                source.datetime = last_modified
                source.save(update_fields=["datetime"])

        do_route_links(feed, source, existing_routes, stops_data, stop_codes)


def do_route_links(
    feed: gtfs_kit.feed.Feed,
    source: DataSource,
    routes: dict,
    stops: dict,
    stop_codes: dict,
):
    try:
        trips = feed.get_trips(as_gdf=True).drop_duplicates("shape_id")
    except ValueError:
        return

    existing_route_links = {
        (rl.service_id, rl.from_stop_id, rl.to_stop_id): rl
        for rl in RouteLink.objects.filter(service__source=source)
    }
    route_links = {}

    for trip in trips.itertuples():
        if trip.geometry is None:
            continue

        service = routes[trip.route_id].service_id

        start_dist = None

        for a, b in pairwise(
            feed.stop_times[feed.stop_times.trip_id == trip.trip_id].itertuples()
        ):
            from_stop = stop_codes.get(a.stop_id, a.stop_id)
            to_stop = stop_codes.get(b.stop_id, b.stop_id)
            key = (service, from_stop, to_stop)

            if key in route_links:
                start_dist = None
                continue

            # find the substring of rl.geometry between the stops a and b
            if not start_dist:
                stop_a = stops[a.stop_id]
                point_a = so.Point(stop_a.stop_lon, stop_a.stop_lat)
                start_dist = trip.geometry.project(point_a)
            stop_b = stops[b.stop_id]
            point_b = so.Point(stop_b.stop_lon, stop_b.stop_lat)
            end_dist = trip.geometry.project(point_b)

            geom = so.substring(trip.geometry, start_dist, end_dist)
            if type(geom) is so.LineString:
                if key in existing_route_links:
                    rl = existing_route_links[key]
                else:
                    rl = RouteLink(
                        service_id=key[0],
                        from_stop_id=key[1],
                        to_stop_id=key[2],
                    )
                rl.geometry = geom.wkt
                route_links[key] = rl

            start_dist = end_dist

    RouteLink.objects.bulk_update(
        [rl for rl in route_links.values() if rl.id], fields=["geometry"]
    )
    RouteLink.objects.bulk_create([rl for rl in route_links.values() if not rl.id])

import logging
from pathlib import Path
from itertools import pairwise

import gtfs_kit
from shapely.errors import EmptyPartError
from shapely import ops as so
from zipfile import BadZipFile
from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.models import Count, Exists, OuterRef, Q
from django.db.models.functions import Now
from django.utils.dateparse import parse_duration

from busstops.models import AdminArea, DataSource, Operator, Region, Service, StopPoint

from ...download_utils import download_if_modified
from ...utils import log_time_taken
from ...models import Route, Trip, RouteLink
from .import_gtfs_ember import get_calendars

logger = logging.getLogger(__name__)

MODES = {
    0: "tram",
    2: "rail",
    3: "bus",
    4: "ferry",
    6: "cable car",
    200: "coach",
    76: "air",  # 1100
}


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Import data even if the GTFS feeds haven't changed",
        )
        parser.add_argument("collections", nargs="*", type=str)

    def handle_operator(self, line):
        agency_id = line.agency_id
        agency_id = f"ie-{agency_id}"

        name = line.agency_name

        operator = Operator.objects.filter(
            Q(name__iexact=name) | Q(noc=agency_id)
        ).first()

        if not operator:
            operator = Operator(name=name, noc=agency_id, url=line.agency_url)
            operator.save()
        elif operator.url != line.agency_url:
            operator.url = line.agency_url
            operator.save(update_fields=["url"])

        return operator

    def do_stops(self, feed: gtfs_kit.feed.Feed) -> dict[str, StopPoint]:
        stops = {}
        admin_areas = {}
        for _, line in feed.stops.iterrows():
            stop_id = line.stop_id
            stop = StopPoint(
                atco_code=stop_id,
                common_name=line.stop_name,
                latlong=GEOSGeometry(f"POINT({line.stop_lon} {line.stop_lat})"),
                locality_centre=False,
                active=True,
                source=self.source,
            )
            if ", stop" in stop.common_name and stop.common_name.count(", ") == 1:
                stop.common_name, stop.indicator = stop.common_name.split(", ")
            stop.common_name = stop.common_name[:48]
            stops[stop_id] = stop
        existing_stops = StopPoint.objects.only(
            "atco_code", "common_name", "latlong"
        ).in_bulk(stops)

        stops_to_create = [
            stop for stop in stops.values() if stop.atco_code not in existing_stops
        ]
        stops_to_update = [
            stop
            for stop in stops.values()
            if stop.atco_code in existing_stops
            and (
                existing_stops[stop.atco_code].latlong != stop.latlong
                or existing_stops[stop.atco_code].common_name != stop.common_name
            )
        ]
        StopPoint.objects.bulk_update(
            stops_to_update, ["common_name", "latlong", "indicator"]
        )

        for stop in stops_to_create:
            admin_area_id = stop.atco_code[:3]
            if admin_area_id not in admin_areas:
                admin_areas[admin_area_id] = AdminArea.objects.filter(
                    id=admin_area_id
                ).exists()
            if admin_areas[admin_area_id]:
                stop.admin_area_id = admin_area_id

        StopPoint.objects.bulk_create(stops_to_create, batch_size=1000)
        return StopPoint.objects.only("atco_code").in_bulk(stops)

    def handle_route(self, line):
        line_name = line.route_short_name if type(line.route_short_name) is str else ""
        description = line.route_long_name if type(line.route_long_name) is str else ""
        if not line_name and " " not in description:
            line_name = description
            if len(line_name) < 5:
                description = ""

        operator = self.operators.get(line.agency_id)
        services = Service.objects.filter(operator=operator)

        q = Exists(
            Route.objects.filter(code=line.route_id, service=OuterRef("id"))
        ) | Q(service_code=line.route_id)

        if line_name and line_name not in ("rail", "InterCity"):
            q |= Q(line_name__iexact=line_name)
        elif description:
            q |= Q(description=description)

        service = services.filter(q).order_by("id").first()
        if not service:
            service = Service(source=self.source)

        service.service_code = line.route_id
        service.line_name = line_name
        service.description = description
        if line.route_type in MODES:
            service.mode = MODES[line.route_type]
        else:
            logger.warning("unknown route type %s", line)
        service.current = True
        service.source = self.source
        service.save()

        if operator:
            if service.id in self.services:
                service.operator.add(operator)
            else:
                service.operator.set([operator])
        self.services[service.id] = service

        route, created = Route.objects.update_or_create(
            {
                "line_name": service.line_name,
                "description": service.description,
                "service": service,
            },
            source=self.source,
            code=line.route_id,
        )
        if not created:
            route.trip_set.all().delete()
        self.routes[line.route_id] = route
        self.route_operators[line.route_id] = operator

    def handle_zipfile(self, path):
        feed = gtfs_kit.read_feed(path, dist_units="km")

        self.operators = {}
        self.routes = {}
        self.route_operators = {}
        self.services = {}

        for agency in feed.agency.itertuples():
            self.operators[agency.agency_id] = self.handle_operator(agency)

        for route in feed.routes.itertuples():
            self.handle_route(route)

        try:
            for route in gtfs_kit.routes.get_routes(feed, as_gdf=True).itertuples():
                self.routes[route.route_id].service.geometry = route.geometry.wkt
                if route.geometry:
                    self.routes[route.route_id].service.save(update_fields=["geometry"])
        except (AttributeError, EmptyPartError, ValueError):
            pass

        stops = self.do_stops(feed)

        calendars = get_calendars(feed, source=self.source)

        trips = {}

        # line as in line in a spreadsheet, not as in the Elizabeth Line
        for line in feed.trips.itertuples():
            route = self.routes[line.route_id]
            trips[line.trip_id] = Trip(
                route=route,
                calendar=calendars[line.service_id],
                inbound=line.direction_id == 1,
                headsign=line.trip_headsign,
                ticket_machine_code=line.trip_id,
                block=getattr(line, "block_id", ""),
                vehicle_journey_code=getattr(line, "trip_short_name", ""),
                operator=self.route_operators[line.route_id],
            )

        # use stop_times.txt to calculate trips' start times, end times and destinations:

        trip = None
        previous_line = None

        for line in feed.stop_times.itertuples():
            if not previous_line or previous_line.trip_id != line.trip_id:
                if trip:
                    trip.destination = stops.get(previous_line.stop_id)
                    trip.end = previous_line.arrival_time

                trip = trips[line.trip_id]
                trip.start = line.departure_time

            previous_line = line

        if previous_line:
            # last trip:
            trip.destination = stops.get(line.stop_id)
            trip.end = line.arrival_time

        for trip_id in trips:
            trip = trips[trip_id]
            if trip.start is None:
                logger.warning(f"trip {trip_id} has no stop times")
                trips[trip_id] = None

        Trip.objects.bulk_create(
            [trip for trip in trips.values() if isinstance(trip, Trip)],
            batch_size=1000,
        )

        with (
            connection.cursor() as cursor,
            cursor.copy(
                "COPY bustimes_stoptime (stop_id, arrival, departure, sequence, trip_id, timing_status, pick_up, set_down, stop_code) FROM STDIN"
            ) as copy,
        ):
            for line in feed.stop_times.itertuples():
                timing_status = "PTP" if getattr(line, "timepoint", 1) == 1 else "OTH"

                pick_up = None
                match line.pickup_type:
                    case 0:  # Regularly scheduled pickup
                        pick_up = True
                    case 1:  # "No pickup available"
                        pick_up = False

                set_down = None
                match line.drop_off_type:
                    case 0:  # Regularly scheduled drop off
                        set_down = True
                    case 1:  # "No drop off available"
                        set_down = False

                departure = int(parse_duration(line.departure_time).total_seconds())
                arrival = None
                if line.arrival_time != departure:
                    arrival = int(parse_duration(line.arrival_time).total_seconds())

                copy.write_row(
                    (
                        line.stop_id,
                        arrival,
                        departure,
                        line.stop_sequence,
                        trips[line.trip_id].pk,
                        timing_status,
                        pick_up,
                        set_down,
                        "",
                    )
                )

        del trips

        services = Service.objects.filter(id__in=self.services.keys())

        for service in services:
            service.do_stop_usages()

            region = (
                Region.objects.filter(adminarea__stoppoint__service=service)
                .annotate(Count("adminarea__stoppoint__service"))
                .order_by("-adminarea__stoppoint__service__count")
                .first()
            )
            if region and region != service.region:
                service.save(update_fields=["region"])

            service.update_search_vector()

        services.update(modified_at=Now())

        self.source.save(update_fields=["datetime"])

        for operator in self.operators.values():
            operator.region = (
                Region.objects.filter(adminarea__stoppoint__service__operator=operator)
                .annotate(Count("adminarea__stoppoint__service__operator"))
                .order_by("-adminarea__stoppoint__service__operator__count")
                .first()
            )
            if operator.region_id:
                operator.save(update_fields=["region"])

        old_routes = self.source.route_set.exclude(
            id__in=(route.id for route in self.routes.values())
        )
        logger.info(old_routes.update(service=None))

        current_services = self.source.service_set.filter(current=True)
        logger.info(
            current_services.exclude(route__in=self.routes.values()).update(
                current=False
            )
        )
        old_routes.update(service=None)

        do_route_links(feed, self.source, self.routes, stops)

    def handle(self, *args, **options):
        collections = DataSource.objects.filter(
            url__startswith="https://www.transportforireland.ie/transitData/Data/GTFS_"
        )

        if options["collections"]:
            collections = collections.filter(name__in=options["collections"])

        for source in collections:
            path: Path = settings.DATA_DIR / Path(source.url).name

            modified, last_modified = download_if_modified(path, source)
            if modified or last_modified != source.datetime or options["collections"]:
                logger.info(f"{source} {last_modified}")
                if last_modified:
                    source.datetime = last_modified
                self.source = source
                try:
                    with log_time_taken(logger):
                        self.handle_zipfile(path)
                except (OSError, BadZipFile) as e:
                    logger.exception(e)

            # sleep(2)


def do_route_links(
    feed: gtfs_kit.feed.Feed, source: DataSource, routes: dict, stops: dict
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
            key = (service, a.stop_id, b.stop_id)

            if key in route_links:
                start_dist = None
                continue

            # find the substring of rl.geometry between the stops a and b
            if not start_dist:
                stop_a = stops[a.stop_id]
                point_a = so.Point(stop_a.latlong.coords)
                start_dist = trip.geometry.project(point_a)
            stop_b = stops[b.stop_id]
            point_b = so.Point(stop_b.latlong.coords)
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

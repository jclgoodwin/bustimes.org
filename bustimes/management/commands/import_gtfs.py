import logging
from pathlib import Path

import gtfs_kit
import pandas as pd
from shapely.errors import EmptyPartError, GEOSException
from zipfile import BadZipFile
from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry
from django.core.management.base import BaseCommand
from django.db.models import Count, Exists, OuterRef, Q
from django.db.models.functions import Now

from busstops.models import AdminArea, DataSource, Operator, Region, Service, StopPoint

from ...download_utils import download_if_modified
from ...models import Route, StopTime, Trip
from .import_gtfs_ember import get_calendars

logger = logging.getLogger(__name__)

MODES = {
    0: "tram",
    2: "rail",
    3: "bus",
    4: "ferry",
    200: "coach",
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

    def do_stops(self, feed: gtfs_kit.feed.Feed):
        stops = {}
        admin_areas = {}
        stops_not_created = {}
        for i, line in feed.stops.iterrows():
            stop_id = line.stop_id
            if stop_id[0] in "78" and len(stop_id) <= 16:
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
            else:
                stops_not_created[stop_id] = line
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
        return StopPoint.objects.only("atco_code").in_bulk(stops), stops_not_created

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
        service.mode = MODES.get(line.route_type, "")
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

        # # exclude Dublin Express routes (they are in the NCSD dataset instead)
        # excluded_agencies = feed.agency[
        #     feed.agency.agency_name == "Dublin Express"
        # ].agency_id
        # feed = feed.restrict_to_routes(
        #     feed.routes[~feed.routes.agency_id.isin(excluded_agencies)].route_id
        # )

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
                self.routes[route.route_id].service.save(update_fields=["geometry"])
        except (ValueError, EmptyPartError, GEOSException):
            pass

        stops, stops_not_created = self.do_stops(feed)

        calendars = get_calendars(feed, source=self.source)

        trips = {}
        headsigns = {}

        for line in feed.trips.itertuples():
            route = self.routes[line.route_id]
            trips[line.trip_id] = Trip(
                route=route,
                calendar=calendars[line.service_id],
                inbound=line.direction_id == 1,
                ticket_machine_code=line.trip_id,
                block=getattr(line, "block_id", ""),
                vehicle_journey_code=getattr(line, "trip_short_name", ""),
                operator=self.route_operators[line.route_id],
            )

            if pd.notna(headsign := line.trip_headsign):
                if headsign.endswith(" -"):
                    headsign = None
                elif headsign.startswith("- "):
                    headsign = headsign[2:]
                if headsign:
                    if line.route_id not in headsigns:
                        headsigns[line.route_id] = {
                            0: set(),
                            1: set(),
                        }
                    headsigns[line.route_id][line.direction_id].add(headsign)

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
                # if line["stop_headsign"]:
                #     if not trip["trip_headsign"]:
                #         trip["trip_headsign"] = line["stop_headsign"]

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

        # headsigns - origins and destinations:

        for route_id in headsigns:
            route = self.routes[route_id]
            origins = headsigns[route_id][1]  # inbound destinations
            destinations = headsigns[route_id][0]  # outbound destinations
            origin = ""
            destination = ""
            if len(origins) <= 1 and len(destinations) <= 1:
                if origins:
                    origin = list(origins)[0]
                if destinations:
                    destination = list(destinations)[0]

                # if headsign contains ' - ' assume it's 'origin - destination', not just destination
                if origin and " - " in origin:
                    route.inbound_description = origin
                    origin = ""
                if destination and " - " in destination:
                    route.outbound_description = destination
                    destination = ""

                route.origin = origin
                route.destination = destination

                route.save(
                    update_fields=[
                        "origin",
                        "destination",
                        "inbound_description",
                        "outbound_description",
                    ]
                )

                if not route.service.description:
                    route.service.description = (
                        route.outbound_description or route.inbound_description
                    )
                    route.service.save(update_fields=["description"])

        i = 0
        stop_times = []

        for line in feed.stop_times.itertuples():
            stop_time = StopTime(
                arrival=line.arrival_time,
                departure=line.departure_time,
                sequence=line.stop_sequence,
                trip=trips[line.trip_id],
                timing_status="PTP" if getattr(line, "timepoint", 1) == 1 else "OTH",
            )
            match line.pickup_type:
                case 0:  # Regularly scheduled pickup
                    stop_time.pick_up = True
                case 1:  # "No pickup available"
                    stop_time.pick_up = False
                case _:
                    assert False
            match line.drop_off_type:
                case 0:  # Regularly scheduled drop off
                    stop_time.set_down = True
                case 1:  # "No drop off available"
                    stop_time.set_down = False
                case _:
                    assert False

            if stop := stops.get(line.stop_id):
                stop_time.stop = stop
            elif stop := stops_not_created.ge(line.stop_id):
                stop_time.stop_code = stop.stop_name
            else:
                stop_time.stop_code = line.stop_id

            if stop_time.arrival == stop_time.departure:
                stop_time.arrival = None

            stop_times.append(stop_time)

            if i == 999:
                StopTime.objects.bulk_create(stop_times)
                stop_times = []
                i = 0
            else:
                i += 1

        StopTime.objects.bulk_create(stop_times)

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

        StopPoint.objects.filter(active=False, service__current=True).update(
            active=True
        )
        StopPoint.objects.filter(active=True, service__isnull=True).update(active=False)

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
                    self.handle_zipfile(path)
                except (OSError, BadZipFile) as e:
                    logger.exception(e)

            # sleep(2)

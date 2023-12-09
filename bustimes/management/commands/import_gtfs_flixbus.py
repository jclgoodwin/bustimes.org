import logging
from pathlib import Path

import gtfs_kit
from django.conf import settings

# from django.contrib.gis.geos import GEOSGeometry, LineString, MultiLineString
from django.core.management.base import BaseCommand
from django.db import transaction

from busstops.models import DataSource, Operator, Service

from ...download_utils import download_if_changed
from ...models import Route, StopTime, Trip
from .import_gtfs_ember import get_calendars

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    def handle(self, *args, **options):
        operator = Operator.objects.get(name="FlixBus")
        source = DataSource.objects.get(name="FlixBus")

        path = settings.DATA_DIR / Path("flixbus_eu.zip")

        url = "https://gtfs.gis.flix.tech/gtfs_generic_eu.zip"

        modified, last_modified = download_if_changed(path, url)
        print(modified, last_modified)
        print("a")

        feed = gtfs_kit.read_feed(path, dist_units="km")

        feed = feed.restrict_to_routes(
            [route_id for route_id in feed.routes.route_id if route_id.startswith("UK")]
        )
        print(feed)
        feed.describe()
        print("b")

        # import ipdb
        # ipdb.set_trace()

        stops_data = {row.stop_id: row for i, row in feed.stops.iterrows()}
        stop_codes = {
            stop_code.code: stop_code.stop_id for stop_code in source.stopcode_set.all()
        }
        # for row in stops_data:
        #     print(f"{row},{stops_data[row].stop_lat},{stops_data[row].stop_lon}")

        # return

        existing_services = {
            service.line_name: service for service in operator.service_set.all()
        }
        existing_routes = {route.code: route for route in source.route_set.all()}
        routes = []

        calendars = get_calendars(feed)

        for i, row in feed.routes.iterrows():
            line_name = row.route_id.removeprefix("UK")

            if line_name in existing_services:
                service = existing_services[line_name]
            else:
                service = Service(line_name=line_name, source=source)

            if row.route_id in existing_routes:
                route = existing_routes[row.route_id]
            else:
                route = Route(code=row.route_id, source=source)
            route.service = service
            route.line_name = line_name
            service.description = route.description = row.route_long_name
            service.current = True
            service.colour_id = operator.colour_id

            service.save()
            service.operator.add(operator)
            route.save()

            routes.append(route)

            existing_routes[route.code] = route  # deals with duplicate rows

        trips = {trip.vehicle_journey_code: trip for trip in operator.trip_set.all()}
        for i, row in feed.trips.iterrows():
            trip = Trip(
                route=existing_routes[row.route_id],
                calendar=calendars[row.service_id],
                inbound=row.direction_id == 1,
                vehicle_journey_code=row.trip_id,
                operator=operator,
            )
            if trip.vehicle_journey_code in trips:
                # reuse existing trip id
                trip.id = trips[trip.vehicle_journey_code].id
            trips[trip.vehicle_journey_code] = trip

        stop_times = []
        for i, row in feed.stop_times.iterrows():
            stop_name = stops_data[row.stop_id].stop_name

            trip = trips[row.trip_id]
            if not trip.start:
                trip.start = row.arrival_time
            trip.end = row.departure_time
            # trip.destination_id = row.stop_id

            stop_time = StopTime(
                arrival=row.arrival_time,
                departure=row.departure_time,
                sequence=row.stop_sequence,
                trip=trip,
                timing_status="PTP" if row.timepoint else "OTH",
            )
            if row.stop_id in stop_codes:
                stop_time.stop_id = stop_codes[row.stop_id]
                print(stop_codes[row.stop_id], row.stop_id)
            else:
                stop_time.stop_code = stop_name

            stop_times.append(stop_time)

        with transaction.atomic():
            Trip.objects.bulk_create([trip for trip in trips.values() if not trip.id])
            existing_trips = [trip for trip in trips.values() if trip.id]
            Trip.objects.bulk_update(
                existing_trips,
                fields=[
                    "route",
                    "calendar",
                    "start",
                    "end",
                    "destination",
                    "block",
                    "ticket_machine_code",
                ],
            )

            StopTime.objects.filter(trip__in=existing_trips).delete()
            StopTime.objects.bulk_create(stop_times)

            print(
                source.route_set.exclude(id__in=[route.id for route in routes]).delete()
            )
            print(
                operator.trip_set.exclude(
                    id__in=[trip.id for trip in trips.values()]
                ).delete()
            )
            print(
                operator.service_set.filter(current=True, route__isnull=True).update(
                    current=False
                )
            )

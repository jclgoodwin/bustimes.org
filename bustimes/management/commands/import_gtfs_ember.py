import logging
from pathlib import Path

import gtfs_kit
from django.conf import settings

# from django.contrib.gis.geos import GEOSGeometry, LineString, MultiLineString
from django.core.management.base import BaseCommand
from django.db import transaction

from busstops.models import DataSource, Operator, Service, StopPoint

from ...download_utils import download_if_changed
from ...models import Calendar, CalendarDate, Route, StopTime, Trip

logger = logging.getLogger(__name__)


def get_calendars(feed) -> dict:
    calendars = {}

    for i, row in feed.calendar.iterrows():
        calendars[row.service_id] = Calendar(
            mon=row.monday,
            tue=row.tuesday,
            wed=row.wednesday,
            thu=row.thursday,
            fri=row.friday,
            sat=row.saturday,
            sun=row.sunday,
            start_date=row.start_date,
            end_date=row.end_date,
        )
    Calendar.objects.bulk_create(calendars.values())

    calendar_dates = []
    for i, row in feed.calendar_dates.iterrows():
        operation = row["exception_type"] == 1  # '1' = operates, '2' = does not operate
        calendar_dates.append(
            CalendarDate(
                calendar=calendars[row.service_id],
                start_date=row.date,
                end_date=row.date,
                operation=operation,
                special=operation,  # additional date of operation
            )
        )
    CalendarDate.objects.bulk_create(calendar_dates)

    return calendars


class Command(BaseCommand):
    def handle(self, *args, **options):
        path = settings.DATA_DIR / Path("ember_gtfs.zip")

        url = "https://api.ember.to/v1/gtfs/static/"

        modified, last_modified = download_if_changed(path, url)
        print(modified, last_modified)
        print("a")

        feed = gtfs_kit.read_feed(path, dist_units="km")
        # print(feed)
        # feed.describe()
        print("b")

        operator = Operator.objects.get(name="Ember")
        source = DataSource.objects.get(name="Ember")

        existing_services = {
            service.line_name: service for service in operator.service_set.all()
        }
        existing_routes = {route.code: route for route in source.route_set.all()}
        routes = []

        stops = StopPoint.objects.in_bulk(feed.stops.stop_id.to_list())

        calendars = get_calendars(feed)

        for i, row in gtfs_kit.routes.geometrize_routes(feed).iterrows():
            if row.route_id in existing_services:
                service = existing_services[row.route_id]
            else:
                service = Service(line_name=row.route_id, source=source)

            if row.route_id in existing_routes:
                route = existing_routes[row.route_id]
            else:
                route = Route(code=row.route_id, source=source)
            route.service = service
            route.line_name = row.route_id
            service.description = route.description = row.route_long_name
            service.current = True
            service.geometry = row.geometry.wkt

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
            trip = trips[row.trip_id]
            if not trip.start:
                trip.start = row.arrival_time
            trip.end = row.departure_time

            stop_time = StopTime(
                arrival=row.arrival_time,
                departure=row.departure_time,
                sequence=row.stop_sequence,
                trip=trip,
                timing_status="PTP" if row.timepoint else "OTH",
            )

            stop_time.stop = trip.destination = stops.get(row.stop_id)

            if stop_time.stop is None:
                stop_time.stop_code = row.stop_id

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

            for service in source.service_set.filter(current=True):
                service.do_stop_usages()
                service.update_search_vector()

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

import logging
from functools import cache
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

import gtfs_kit
import requests
from google.transit import gtfs_realtime_pb2
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from busstops.models import DataSource, Operator, Service, StopPoint

from ...download_utils import download_if_modified
from ...models import Calendar, CalendarDate, Route, StopTime, Trip, Note

logger = logging.getLogger(__name__)


@cache
def get_note(note_code, note_text):
    return Note.objects.get_or_create(code=note_code or "", text=note_text[:255])[0]


def get_calendars(feed, source) -> dict:
    calendars = {
        row.service_id: Calendar(
            mon=row.monday,
            tue=row.tuesday,
            wed=row.wednesday,
            thu=row.thursday,
            fri=row.friday,
            sat=row.saturday,
            sun=row.sunday,
            start_date=row.start_date,
            end_date=row.end_date,
            source=source,
        )
        for row in feed.calendar.itertuples()
    }

    calendar_dates = []

    if feed.calendar_dates is not None:
        for row in feed.calendar_dates.itertuples():
            operation = row.exception_type == 1
            # 1: operates, 2: does not operate

            if (calendar := calendars.get(row.service_id)) is None:
                calendar = Calendar(
                    start_date=row.date,  # dummy date
                )
                calendars[row.service_id] = calendar
            calendar_dates.append(
                CalendarDate(
                    calendar=calendar,
                    start_date=row.date,
                    end_date=row.date,
                    operation=operation,
                    special=operation,  # additional date of operation
                )
            )

    Calendar.objects.bulk_create(calendars.values())
    CalendarDate.objects.bulk_create(calendar_dates)

    return calendars


def get_last_modified(path):
    info = ZipFile(path).infolist()
    return datetime(*info[0].date_time, tzinfo=timezone.utc)


class Command(BaseCommand):
    def handle(self, *args, **options):
        path = settings.DATA_DIR / Path("ember_gtfs.zip")

        source = DataSource.objects.get(name="Ember")
        source.url = "https://api.ember.to/v1/gtfs/static/"

        modified, last_modified = download_if_modified(path, source)
        assert modified

        # there's no last-modified header so use the contents of the zipfile
        if not last_modified:
            last_modified = get_last_modified(path)

        if source.datetime == last_modified:
            return  # no new data to import
        source.datetime = last_modified

        print(f"{source} {last_modified}")

        feed = gtfs_kit.read_feed(path, dist_units="km")

        operator = Operator.objects.get(name="Ember")

        existing_services = {
            service.line_name: service for service in operator.service_set.all()
        }
        existing_routes = {route.code: route for route in source.route_set.all()}
        routes = []

        stops = StopPoint.objects.in_bulk(feed.stops.stop_id.to_list())
        new_stops = [
            StopPoint(
                atco_code=f"ember-{stop.stop_id}",
                common_name=stop.stop_name,
                active=True,
                source=source,
                latlong=f"POINT({stop.stop_lon} {stop.stop_lat})",
            )
            for stop in feed.stops.itertuples()
            if stop.stop_id not in stops
        ]
        StopPoint.objects.bulk_create(
            new_stops,
            update_conflicts=True,
            unique_fields=["atco_code"],
            update_fields=["common_name", "latlong"],
        )
        for stop in new_stops:
            stops[stop.atco_code.removeprefix("ember-")] = stop

        calendars = get_calendars(feed, source)

        for row in feed.get_routes(as_gdf=True).itertuples():
            if row.route_id in existing_services:
                service = existing_services[row.route_id]
            else:
                service = Service(line_name=row.route_id)

            if row.route_id in existing_routes:
                route = existing_routes[row.route_id]
            else:
                route = Route(code=row.route_id)
            route.source = source
            route.service = service
            route.line_name = row.route_id
            service.source = source
            service.description = route.description = row.route_long_name
            service.current = True
            service.colour_id = operator.colour_id
            if row.geometry:
                service.geometry = row.geometry.wkt

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
            trip = Trip(
                route=existing_routes[row.route_id],
                calendar=calendars[row.service_id],
                inbound=row.direction_id == 1,
                vehicle_journey_code=row.trip_id,
                operator=operator,
                headsign=row.trip_headsign,
            )
            if trip.vehicle_journey_code in existing_trips:
                # reuse existing trip id
                trip.id = existing_trips[trip.vehicle_journey_code].id
            trips[trip.vehicle_journey_code] = trip
        del existing_trips

        stop_times = []
        for row in feed.stop_times.itertuples():
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
                pick_up=(row.pickup_type != 1),
                set_down=(row.drop_off_type != 1),
            )

            stop_time.stop = trip.destination = stops[row.stop_id]

            stop_times.append(stop_time)

        # get TripUpdates from the GTFS-RT feed - to mark some stops as "pre-book only":

        realtime_url = "https://api.ember.to/v1/gtfs/realtime/"
        response = requests.get(realtime_url, timeout=10)
        response.raise_for_status()

        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(response.content)

        stop_notes = {}  # map of notes to lists of stop ids

        for item in feed.entity:
            if item.HasField("alert"):
                header = item.alert.header_text.translation[0].text
                description = item.alert.description_text.translation[0].text
                if header == "Pre-booking":
                    stop_id = item.alert.informed_entity[0].stop_id
                    note = get_note("b", description)
                    if note in stop_notes:
                        stop_notes[note].append(stop_id)
                    else:
                        stop_notes[note] = [stop_id]

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
                    "vehicle_journey_code",
                    "inbound",
                    "headsign",
                ],
            )

            StopTime.objects.filter(trip__in=existing_trips).delete()
            StopTime.objects.bulk_create(stop_times)

            existing_notes = {
                (note.code, note.text): note
                for note in Note.objects.filter(trip__operator="EMBR")
            }
            for note, stop_ids in stop_notes.items():
                note_stop_times = [
                    stop_time
                    for stop_time in stop_times
                    if stop_time.stop_id in stop_ids
                ]
                note_trips = [stop_time.trip_id for stop_time in stop_times]
                note.stoptime_set.set(note_stop_times)
                note.trip_set.set(note_trips)

            # remove old notes
            for note in existing_notes.values():
                if note not in stop_notes:
                    note.trip_set.clear()

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

            source.save(update_fields=["url", "datetime"])

import logging
from functools import cache
from itertools import pairwise
from pathlib import Path
import geopandas as gpd

import gtfs_kit
import requests
from google.transit import gtfs_realtime_pb2
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Min, Subquery, OuterRef
from django.contrib.gis.geos import LineString, Point

from busstops.models import DataSource, Operator, Service, StopPoint
from vosa.models import Registration

from ...download_utils import download_if_modified
from ...models import Route, StopTime, Trip, Note, RouteLink
from ...gtfs_utils import get_calendars, MODES

logger = logging.getLogger(__name__)


note_codes = ["¶", "‖", "§", "‡", "†", "*"]


@cache
def get_note(note_text):
    return Note.objects.get_or_create(code=note_codes.pop(), text=note_text[:255])[0]


class Command(BaseCommand):
    def handle(self, *args, **options):
        path = settings.DATA_DIR / Path("ember_gtfs.zip")

        source = DataSource.objects.get(name="Ember")
        source.url = "https://cdn.ember.to/gtfs/static/Ember_GTFS_latest.zip"

        modified, last_modified = download_if_modified(path, source)

        if not modified:
            return  # no new data to import
        source.datetime = last_modified

        logger.info(f"{source} {last_modified}")

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
            service.route_type = MODES[row.route_type]
            if row.geometry:
                service.geometry = row.geometry.wkt

            registrations = Registration.objects.filter(
                licence__licence_number="PM2025892", service_number=row.route_id
            )
            if len(registrations) == 1:
                route.registration = registrations[0]

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

        existing_route_links = {
            (rl.service.line_name, rl.from_stop_id, rl.to_stop_id): rl
            for rl in RouteLink.objects.filter(service__in=existing_services.values())
        }
        route_links = {}

        for trip in feed.trips.itertuples():
            service = existing_routes[trip.route_id].service

            shape = feed.shapes[feed.shapes.shape_id == trip.shape_id]
            shape_gdf = gpd.GeoDataFrame(
                shape,
                geometry=gpd.points_from_xy(shape.shape_pt_lon, shape.shape_pt_lat),
                crs="EPSG:4326",
            )
            if shape_gdf.empty:
                continue

            for a, b in pairwise(
                feed.stop_times[feed.stop_times.trip_id == trip.trip_id].itertuples()
            ):
                from_stop = stops[a.stop_id]
                to_stop = stops[b.stop_id]
                key = (trip.route_id, from_stop.atco_code, to_stop.atco_code)

                if key in route_links:
                    continue

                segment_gdf = shape_gdf[
                    (shape_gdf.shape_dist_traveled >= a.shape_dist_traveled)
                    & (shape_gdf.shape_dist_traveled <= b.shape_dist_traveled)
                ]
                if segment_gdf.empty:
                    continue

                if key in existing_route_links:
                    rl = existing_route_links[key]
                else:
                    rl = RouteLink(
                        service=service,
                        from_stop=from_stop,
                        to_stop=to_stop,
                    )
                rl.geometry = LineString(
                    *(Point(p.x, p.y) for p in segment_gdf.geometry.values)
                )
                route_links[key] = rl

        RouteLink.objects.bulk_update(
            [rl for rl in route_links.values() if rl.id], fields=["geometry"]
        )
        RouteLink.objects.bulk_create([rl for rl in route_links.values() if not rl.id])

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
                    note = get_note(description)
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
                note_trips = [stop_time.trip_id for stop_time in note_stop_times]
                note.stoptime_set.set(note_stop_times)
                note.trip_set.set(note_trips)

            # remove old notes
            for note in existing_notes.values():
                if note not in stop_notes:
                    note.trip_set.clear()

            for service in source.service_set.filter(current=True):
                service.do_stop_usages()
                service.update_search_vector()

            logger.info(
                source.route_set.exclude(id__in=[route.id for route in routes]).delete()
            )
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

            source.route_set.update(
                start_date=Subquery(
                    Route.objects.filter(pk=OuterRef("pk"))
                    .annotate(min_date=Min("trip__calendar__start_date"))
                    .values("min_date")[:1]
                )
            )

            source.save(update_fields=["url", "datetime"])

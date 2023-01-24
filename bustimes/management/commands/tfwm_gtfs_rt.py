import io
import zipfile
from datetime import datetime, timezone

import requests_cache
from django.core.cache import cache
from django.core.management.base import BaseCommand
from google.transit import gtfs_realtime_pb2

from busstops.models import DataSource

from .import_gtfs import read_file


class Command(BaseCommand):
    def get_routes_and_trips(self, session, source):
        routes = {}
        trips = {}

        gtfs_url = "http://api.tfwm.org.uk/gtfs/tfwm_gtfs.zip"
        response = session.get(gtfs_url, params=source.settings)

        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            for line in read_file(archive, "routes.txt"):
                routes[line["route_id"]] = line

            for line in read_file(archive, "trips.txt"):
                trips[line["trip_id"]] = line

        return routes, trips

    def handle(self, *args, **options):
        source = DataSource.objects.get(name="TfWM")

        session = requests_cache.CachedSession(cache_control=True)

        routes, trips = self.get_routes_and_trips(session, source)

        url = "http://api.tfwm.org.uk/gtfs/trip_updates"

        response = session.get(url, params=source.settings)

        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(response.content)

        by_stop = {}

        for item in feed.entity:

            prev = None

            for stop_time_update in item.trip_update.stop_time_update:
                if stop_time_update.departure.time:

                    departure = {
                        "expected_departure_time": datetime.fromtimestamp(
                            stop_time_update.departure.time
                            - stop_time_update.departure.delay,
                            timezone.utc,
                        ),
                        "aimed_departure_time": datetime.fromtimestamp(
                            stop_time_update.departure.time, timezone.utc
                        ),
                        "destination": trips[item.trip_update.trip.trip_id][
                            "trip_headsign"
                        ],
                        "line_name": routes[
                            trips[item.trip_update.trip.trip_id]["route_id"]
                        ]["route_short_name"],
                        "vehicle": item.trip_update.vehicle.id,
                    }

                    if (stop_id := stop_time_update.stop_id) not in by_stop:
                        by_stop[stop_id] = []
                    by_stop[stop_id].append(departure)
                # else:
                #     print(stop_time_update.departure)

                if prev:
                    if not (prev.stop_sequence == stop_time_update.stop_sequence - 1):
                        print(item.trip_update.trip.trip_id)
                        print(prev.stop_sequence, stop_time_update.stop_sequence)
                prev = stop_time_update

        # print(by_stop)

        if by_stop:
            cache.set_many(by_stop, 600)

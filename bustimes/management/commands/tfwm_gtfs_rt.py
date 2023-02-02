import io
import zipfile

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
        print(response.from_cache)

        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            for line in read_file(archive, "routes.txt"):
                routes[line["route_id"]] = line

            for line in read_file(archive, "trips.txt"):
                trips[line["trip_id"]] = line

        return routes, trips

    def handle(self, *args, **options):
        source = DataSource.objects.get(name="TfWM")

        session = requests_cache.CachedSession(cache_control=True, expire_after=60)

        routes, trips = self.get_routes_and_trips(session, source)

        url = "http://api.tfwm.org.uk/gtfs/trip_updates"

        response = session.get(url, params=source.settings)
        print(response.from_cache)

        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(response.content)

        by_stop = {}

        for item in feed.entity:

            prev = None

            for stop_time_update in item.trip_update.stop_time_update:
                if stop_time_update.departure.time:

                    departure = {
                        "time": stop_time_update.departure.time,
                        "delay": stop_time_update.departure.delay,
                        "destination": trips[item.trip_update.trip.trip_id][
                            "trip_headsign"
                        ],
                        "line_name": routes[
                            trips[item.trip_update.trip.trip_id]["route_id"]
                        ]["route_short_name"],
                        "vehicle": item.trip_update.vehicle.id,
                    }

                    if (key := f"tfwm:{stop_time_update.stop_id}") not in by_stop:
                        by_stop[key] = []
                    by_stop[key].append(departure)
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
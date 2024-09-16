import io
import csv
import zipfile

import requests_cache
from django.core.cache import cache
from django.core.management.base import BaseCommand
from google.transit import gtfs_realtime_pb2

from busstops.models import DataSource


def read_file(archive, name):
    try:
        with archive.open(name) as open_file:
            with io.TextIOWrapper(open_file, encoding="utf-8-sig") as wrapped_file:
                yield from csv.DictReader(wrapped_file)
    except KeyError:
        # file doesn't exist
        return


class Command(BaseCommand):
    def get_routes_and_trips(self, session, source):
        routes = {}
        trips = {}

        gtfs_url = "http://api.tfwm.org.uk/gtfs/tfwm_gtfs.zip"
        response = session.get(gtfs_url, params=source.settings)
        if not response.from_cache:  # new data
            print(response.headers)

        if not response.ok:
            print(response, response.content)

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
        if response.from_cache:  # weird, stale data
            print(response.headers)

        if not response.ok:
            return

        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(response.content)

        by_stop = {}

        for item in feed.entity:
            try:
                trip = trips[item.trip_update.trip.trip_id]
                route = routes[trip["route_id"]]
            except KeyError:
                continue

            for stop_time_update in item.trip_update.stop_time_update:
                if stop_time_update.departure.time:
                    departure = {
                        "time": stop_time_update.departure.time,
                        "delay": stop_time_update.departure.delay,
                        "destination": trip["trip_headsign"],
                        "line_name": route["route_short_name"],
                        "vehicle": item.trip_update.vehicle.id,
                    }

                    if (key := f"tfwm:{stop_time_update.stop_id}") not in by_stop:
                        by_stop[key] = []
                    by_stop[key].append(departure)

        if by_stop:
            cache.set_many(by_stop, 600)

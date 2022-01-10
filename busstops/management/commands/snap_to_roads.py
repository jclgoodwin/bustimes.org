import requests
import polyline

from shapely.geometry import Point, LineString
from shapely.ops import substring

from django.contrib.postgres.aggregates import StringAgg

from django.core.management.base import BaseCommand
from bustimes.models import Trip, RouteLink


class Command(BaseCommand):
    @staticmethod
    def add_arguments(parser):
        parser.add_argument('api_key', type=str)

    def handle(self, api_key, **options):
        session = requests.Session()
        session.params.update({
            'api_key': api_key,
        })
        url = "https://api.stadiamaps.com/trace_route"

        trips = Trip.objects.filter(route__service=4464)
        trips = trips.annotate(
            pattern=StringAgg('stoptime__stop', ':')
        )

        patterns = set()

        for trip in trips:
            if trip.pattern in patterns:
                continue
            patterns.add(trip.pattern)
            print(trip.pattern)

            stop_times = trip.stoptime_set.filter(stop__latlong__isnull=False).select_related('stop')
            self.handle_trip(session, url, trip, stop_times)

    def handle_trip(self, session, url, trip, stop_times):
        points = [
            {
                'lat': stop_time.stop.latlong.y,
                'lon': stop_time.stop.latlong.x,
                'time': stop_time.arrival_or_departure().total_seconds()
            } for stop_time in stop_times
        ]
        response = session.post(url, json={
            'costing': 'bus',
            'shape': points,
            # 'shape_match': 'map_snap',
            'trace_options': {
                'search_radius': 10,
            }
        }).json()

        print(trip)

        for match in [response['trip']] + [alt['trip'] for alt in response['alternates']]:

            assert len(match['locations']) == 2
            assert len(match['legs']) == 1

            leg = match['legs'][0]
            shape = leg['shape']
            shape = polyline.decode(shape)
            shape = LineString([(lon / 10, lat / 10) for lat, lon in shape])

            from_location, to_location = match['locations']

            for from_index in range(from_location['original_index'], to_location['original_index']):
                to_index = from_index + 1

                from_stop = stop_times[from_index].stop
                to_stop = stop_times[to_index].stop

                if RouteLink.objects.filter(
                    service_id=trip.route.service_id,
                    from_stop=from_stop,
                    to_stop=to_stop,
                ).exists():
                    continue

                from_point = Point(from_stop.latlong.coords)
                to_point = Point(to_stop.latlong.coords)

                line_substring = substring(shape, shape.project(from_point), shape.project(to_point))

                RouteLink.objects.create(
                    service_id=trip.route.service_id,
                    from_stop=from_stop,
                    to_stop=to_stop,
                    geometry=line_substring.wkt
                )

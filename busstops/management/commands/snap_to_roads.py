import requests
import polyline
from time import sleep
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point, LineString, MultiLineString
from bustimes.models import Trip
from ...models import Service


class Command(BaseCommand):
    @staticmethod
    def add_arguments(parser):
        parser.add_argument('api_key', type=str)

    def handle(self, api_key, **options):
        session = requests.Session()
        params = {
            'api_key': api_key,
        }

        for service in Service.objects.filter(current=True, operator='LYNX'):
            print(service)
            linestrings = []
            for trip in Trip.objects.filter(route__service=service).distinct('journey_pattern'):
                points = [
                    {
                        'lat': stoptime.stop.latlong.y,
                        'lon': stoptime.stop.latlong.x,
                        'time': stoptime.arrival.total_seconds()
                    } for stoptime in trip.stoptime_set.all()
                ]
                r = session.post('https://api.stadiamaps.com/trace_route', params=params, json={
                    'costing': 'bus',
                    'shape': points,
                    # 'shape_match': 'map_snap',
                    'trace_options': {
                        'search_radius': 100,
                    }
                })
                if r.ok:
                    response = r.json()
                    if len(response['trip']['legs']) > 1:
                        print(response)
                    for leg in response['trip']['legs']:
                        shape = response['trip']['legs'][0]['shape']
                    linestrings.append(LineString(*[Point(lon / 10, lat / 10) for lat, lon in polyline.decode(shape)]))
                sleep(0.1)
            service.geometry = MultiLineString(*linestrings)
            service.save(update_fields=['geometry'])

import requests
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from ...models import Region, StopPoint, Operator


def import_stops(region, session):
    stops = session.get(
        'http://www.bus-man.com/BusMap/BusStopMarkers',
        params={
            'NthEstLat': '54.54',
            'NthEstLng': '-3.8999999999999773',
            'SthWstLat': '53.9',
            'SthWstLng': '-5.2000000000000455',
        }
    ).json()
    for stop in stops:
        defaults = {
            'common_name': stop['CommonName'],
            'latlong': Point(stop['Longitude'], stop['Latitude']),
            'locality_centre': False,
            'active': True
        }
        StopPoint.objects.update_or_create(defaults, atco_code=stop['StopPointRef'])


class Command(BaseCommand):
    def handle(self, *args, **options):

        region = Region.objects.update_or_create(id='IM', defaults={'name': 'Isle of Man'})[0]
        Operator.objects.update_or_create(id='bus-vannin', name='Bus Vannin', region=region)[0]

        session = requests.Session()
        import_stops(region, session)

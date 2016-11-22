"""Usage:

    ./manage.py enhance_ni_stops
"""

import requests
from time import sleep
from django.core.management.base import BaseCommand
from ...models import StopPoint


SESSION = requests.Session()


class Command(BaseCommand):
    def handle(self, *args, **options):
        for stop in StopPoint.objects.filter(atco_code__startswith='7000', service__current=True,
                                             town=''):
            response = SESSION.get('http://nominatim.openstreetmap.org/reverse', params={
                'format': 'json',
                'lon': stop.latlong.x,
                'lat': stop.latlong.y
            }).json()
            print(stop.atco_code)
            print(response)
            stop.street = response['address']['road']
            stop.town = response['address'].get('locality', '')
            stop.save()
            sleep(1)

"""Usage:

    ./manage.py enhance_ni_stops
"""

from time import sleep
import requests
from django.core.management.base import BaseCommand
from ...models import StopPoint


SESSION = requests.Session()
NON_LANDMARK_KEYS = {'road', 'state', 'country_code', 'city', 'county', 'locality', 'country',
                     'suburb', 'town', 'postcode', 'bus_stop', 'village', 'house_number'}


class Command(BaseCommand):
    delay = 2

    def handle(self, *args, **options):
        stops = StopPoint.objects.filter(
            atco_code__startswith='7000',
            town='',
            landmark='',
            service__current=True
        ).distinct()

        for stop in stops:
            response = SESSION.get('http://nominatim.openstreetmap.org/reverse', params={
                'format': 'json',
                'lon': stop.latlong.x,
                'lat': stop.latlong.y
            }).json()

            print(stop.pk)
            stop.street = response['address'].get('road', '')
            stop.town = response['address'].get('locality', '')

            landmark_keys = list(set(response['address'].keys()) - NON_LANDMARK_KEYS)
            if len(landmark_keys) > 0:
                for key in landmark_keys:
                    if len(response['address'][key]) <= 48:
                        stop.landmark = response['address'][key]
                        break
                print(landmark_keys)
                print(stop.landmark)

            stop.save()
            sleep(self.delay)

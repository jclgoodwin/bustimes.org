"""Usage:

    ./manage.py enhance_ni_stops
"""

from time import sleep
import requests
from django.core.management.base import BaseCommand
from ...models import StopPoint, AdminArea


SESSION = requests.Session()
NON_LANDMARK_KEYS = {'road', 'state', 'country_code', 'city', 'county', 'locality', 'country',
                     'suburb', 'town', 'postcode', 'bus_stop', 'village', 'house_number',
                     'hamlet', 'state_district', 'city_district'}


class Command(BaseCommand):
    delay = 2

    def handle(self, *args, **options):
        regions = {'NI', 'UL', 'MU', 'MO', 'CO', 'LE'}
        areas = {area.name: area.id for area in AdminArea.objects.filter(region__in=regions) if area.name}

        stops = StopPoint.objects.filter(
            atco_code__startswith='7000',
            osm__isnull=True
        ).distinct()

        for stop in stops:
            response = SESSION.get('http://nominatim.openstreetmap.org/reverse', params={
                'format': 'json',
                'lon': stop.latlong.x,
                'lat': stop.latlong.y
            }).json()

            print(stop.pk)
            stop.osm = response
            stop.street = response['address'].get('road', '')
            stop.town = response['address'].get('town', '')
            if 'county' in response['address']:
                county = response['address']['county']
                if county in areas:
                    stop.admin_area_id = areas[county]
                else:
                    print(response['address'])
            else:
                print(response['address'])

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

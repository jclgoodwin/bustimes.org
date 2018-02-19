import os
import json
from titlecase import titlecase
from bs4 import BeautifulSoup
from datetime import datetime
from django.conf import settings
from django.contrib.gis.geos import Polygon
from django.core.management.base import BaseCommand
from ...models import DataSource, Place


class Command(BaseCommand):
    def handle(self, *args, **options):
        defaults = {'datetime': datetime.now()}
        regions = DataSource.objects.get_or_create(name='Singapore regions', defaults=defaults)[0]
        # constituencies = DataSource.objects.get_or_create(name='Singapore constituencies', defaults=defaults)[0]
        subzones = DataSource.objects.get_or_create(name='Singapore subzones', defaults=defaults)[0]

        # Regions:

        with open(os.path.join(settings.DATA_DIR, 'singapore.geojson')) as open_file:
            features = json.load(open_file)['features']

        for feature in features:
            assert len(feature['geometry']['coordinates']) == 1
            assert len(feature['geometry']['coordinates'][0]) == 1
            name = feature['properties']['name'].replace(' Community Development Council', '')
            Place.objects.update_or_create(source=regions, name=name, defaults={
                'code': name,
                'polygon': Polygon(feature['geometry']['coordinates'][0][0])
            })

        # Subzones

        with open(os.path.join(settings.DATA_DIR, 'singapore.kml')) as open_file:
            soup = BeautifulSoup(open_file, 'html.parser')

        for place in soup.find_all('placemark'):
            name = titlecase(place.find('name').text)
            polygon = (point.strip().split(',') for point in place.find('coordinates').text.split(',0'))
            polygon = [(float(point[0].strip()), float(point[1].strip())) for point in polygon if len(point) == 2]
            Place.objects.update_or_create(name=name, source=subzones, defaults={
                'code': name,
                'polygon': Polygon(polygon)
            })

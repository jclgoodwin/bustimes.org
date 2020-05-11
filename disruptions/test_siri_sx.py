import os
from vcr import use_cassette
from django.test import TestCase
# from django.contrib.gis.geos import Point
from django.conf import settings
from django.core.management import call_command
from busstops.models import Region
from .models import Disruption


class SiriSXTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Region.objects.create(id='EA', name='East Anglia')
        # DataSource.objects.create(name='Arriva')
        # DataSource.objects.create(name='TransMach')
        # Operator.objects.create(region_id='EA', id='ANWE', name='Arrivederci')
        # Operator.objects.create(region_id='EA', id='GOCH', name='Go-Coach')
        # StopPoint.objects.bulk_create([
        #     StopPoint(pk='069000023592', active=True, latlong=Point(0, 0)),
        #     StopPoint(pk='0690WNA02877', active=True, latlong=Point(0, 0)),
        #     StopPoint(pk='0690WNA02861', active=True, latlong=Point(0, 0)),
        # ])

    def test_siri_sx(self):
        with use_cassette(os.path.join(settings.DATA_DIR, 'vcr', 'siri_sx.yaml'), match_on=['body']):
            call_command('import_siri_sx', 'hen hom', 'roger poultry')

        disruption = Disruption.objects.first()
        response = self.client.get(disruption.get_absolute_url())

        print(response.content.decode())

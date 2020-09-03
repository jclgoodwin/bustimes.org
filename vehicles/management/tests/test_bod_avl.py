import os
from vcr import use_cassette
from django.conf import settings
from django.test import TestCase
from busstops.models import Region, DataSource, Operator
from ...models import VehicleLocation
from ..commands import import_bod_avl


class BusOpenDataVehicleLocationsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        region = Region.objects.create(id='EA')
        Operator.objects.bulk_create([
            Operator(id='ARHE', region=region),
            Operator(id='ASES', region=region),
            Operator(id='CBBH', region=region),
            Operator(id='GPLM', region=region),
            Operator(id='KCTB', region=region),
            Operator(id='WHIP', region=region),
            Operator(id='UNOE', region=region),
        ])
        cls.source = DataSource.objects.create(
            name='Bus Open Data',
            url='https://data.bus-data.dft.gov.uk/avl/download/bulk_archive'
        )

    def test_handle(self):
        command = import_bod_avl.Command()
        command.source = self.source

        with use_cassette(os.path.join(settings.DATA_DIR, 'vcr', 'bod_avl.yaml')):
            command.update()

        self.assertEqual(835, VehicleLocation.objects.count())

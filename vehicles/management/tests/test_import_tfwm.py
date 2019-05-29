import os
from freezegun import freeze_time
from vcr import use_cassette
from django.test import TestCase
from busstops.models import Region, Operator, DataSource
from ...models import Vehicle
from ..commands import import_tfwm


class TfWMImportTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.source = DataSource.objects.create(datetime='2018-08-06T22:41:15+01:00', name='TfWM')
        Region.objects.create(id='WM')
        Operator.objects.create(id='SLBS', region_id='WM', name='Select Bus Services')
        Operator.objects.create(id='FSMR', region_id='WM', name='First Midland Red')

    @use_cassette(os.path.join('data', 'vcr', 'import_tfwm.yaml'), decode_compressed_response=True)
    @freeze_time('2018-08-21 00:00:09')
    def test_handle(self):
        command = import_tfwm.Command()

        command.source = self.source

        items = command.get_items()

        with self.assertNumQueries(1120):
            for item in items:
                command.handle_item(item, self.source.datetime)

        with self.assertNumQueries(824):
            for item in items:
                command.handle_item(item, self.source.datetime)

        self.assertEqual(137, Vehicle.objects.all().count())

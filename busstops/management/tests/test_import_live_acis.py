import os
from vcr import use_cassette
from django.test import TestCase
from ...models import Region, Operator, VehicleLocation
from ..commands import import_live_acis


class SiriVMImportTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Region.objects.create(id='NI')
        cls.operator = Operator.objects.create(id='MET', region_id='NI')
        cls.operator = Operator.objects.create(id='GDR', region_id='NI')

    @use_cassette(os.path.join('data', 'vcr', 'import_live_acis.yaml'))
    def test_handle(self):
        command = import_live_acis.Command()

        with use_cassette(os.path.join('data', 'vcr', 'import_live_acis.yaml'), match_on=['body']):
            command.update()

        # Should only create 18 items - two are duplicates
        self.assertEqual(18, VehicleLocation.objects.all().count())

        with use_cassette(os.path.join('data', 'vcr', 'import_live_acis.yaml'), match_on=['body']):
            command.update()

        # Should create no new items - no changes
        self.assertEqual(18, VehicleLocation.objects.all().count())

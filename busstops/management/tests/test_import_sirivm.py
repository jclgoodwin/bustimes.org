import os
from vcr import use_cassette
from django.test import TestCase
from ...models import DataSource
from ..commands import import_sirivm


class SiriVMImportTest(TestCase):
    @use_cassette(os.path.join('data', 'vcr', 'import_sirivm.yaml'), decode_compressed_response=True)
    def test_handle(self):
        command = import_sirivm.Command()
        items = command.get_items()
        item = next(items)

        command.source = DataSource.objects.create(datetime='2018-08-06T22:41:15+01:00')

        vehicle, created, service = command.get_vehicle_and_service(item)

        self.assertEqual('FE 69532', str(vehicle))
        self.assertTrue(created)
        self.assertIsNone(service)

        location = command.create_vehicle_location(item, vehicle, service)
        self.assertEqual('2018-08-06 21:44:32+01:00', str(location.datetime))
        self.assertIsNone(location.heading)

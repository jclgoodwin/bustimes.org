import os
from vcr import use_cassette
# from mock import patch
from django.test import TestCase
from ...models import DataSource
# with patch('time.sleep', return_value=None):
from ..commands import import_sirivm


@use_cassette(os.path.join('data', 'vcr', 'import_sirivm.yaml'), decode_compressed_response=True)
class SiriVMImportTest(TestCase):
    def test_handle(self):
        command = import_sirivm.Command()
        items = command.get_items()
        item = next(items)

        command.source = DataSource.objects.create(datetime='2018-08-06T22:41:15+01:00')

        vehicle, created, service = command.get_vehicle_and_service(item)

        self.assertEqual('FE 67162', str(vehicle))
        self.assertTrue(created)
        self.assertIsNone(service)

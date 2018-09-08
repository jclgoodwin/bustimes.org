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
        self.assertEqual(-471, location.early)

        locations = command.source.vehiclelocation_set

        command.handle_item(item, None)
        self.assertIsNone(locations.get().heading)

        # if datetime is the same, shouldn't create new vehicle location
        command.handle_item(item, None)
        self.assertEqual(1, command.source.vehiclelocation_set.count())

        # different datetime - should create new vehicle location
        item.find('siri:RecordedAtTime', import_sirivm.NS).text = '2018-08-06T21:45:32+01:00'
        command.handle_item(item, None)
        self.assertEqual(2, command.source.vehiclelocation_set.count())
        self.assertEqual(0, command.source.vehiclelocation_set.last().heading)

        # test an item with an invalid delay ('-PT2M.492S')
        item = next(items)
        location = command.create_vehicle_location(item, vehicle, service)
        self.assertIsNone(location.early)

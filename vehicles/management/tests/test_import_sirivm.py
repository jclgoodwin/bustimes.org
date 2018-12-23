import os
from vcr import use_cassette
from django.test import TestCase
from busstops.models import Region, Operator, Service, DataSource
from ...models import VehicleLocation
from ..commands import import_sirivm


class SiriVMImportTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Region.objects.create(id='EA')
        cls.operator = Operator.objects.create(id='FESX', region_id='EA')
        cls.service = Service.objects.create(line_name='73', date='2010-01-01')
        cls.service.operator.set(['FESX'])

    @use_cassette(os.path.join('data', 'vcr', 'import_sirivm.yaml'), decode_compressed_response=True)
    def test_handle(self):
        command = import_sirivm.Command()
        items = command.get_items()
        item = next(items)

        command.source = DataSource.objects.create(datetime='2018-08-06T22:41:15+01:00')

        vehicle, created, service = command.get_vehicle_and_service(item)

        self.assertEqual('69532', str(vehicle))
        self.assertTrue(created)
        self.assertEqual(self.service, service)
        self.assertEqual(self.operator, vehicle.operator)

        location = command.create_vehicle_location(item, vehicle, service)
        self.assertEqual('2018-08-06 21:44:32+01:00', str(location.datetime))
        self.assertIsNone(location.heading)

        locations = VehicleLocation.objects.filter(journey__source=command.source)

        command.handle_item(item, None)
        self.assertIsNone(locations.get().heading)

        # if datetime is the same, shouldn't create new vehicle location
        command.handle_item(item, None)
        self.assertEqual(1, locations.count())

        # different datetime - should create new vehicle location
        item.find('siri:RecordedAtTime', import_sirivm.NS).text = '2018-08-06T21:45:32+01:00'
        command.handle_item(item, None)
        self.assertEqual(2, locations.count())
        self.assertIsNone(locations.last().heading)

        # test an item with an invalid delay ('-PT2M.492S')
        item = next(items)
        location = command.create_vehicle_location(item, vehicle, service)
        self.assertIsNone(location.early)

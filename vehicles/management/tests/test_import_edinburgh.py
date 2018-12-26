from django.test import TestCase
from busstops.models import DataSource, Service, Operator, Region
from ...models import Vehicle
from ..commands.import_edinburgh import Command


class EdinburghImportTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        source = DataSource.objects.create(name='TfE', url='', datetime='1066-01-01 12:18Z')
        Region.objects.create(name='Scotch Land', id='S')
        cls.operator = Operator.objects.create(name="Ainsley's Chariots", id='AINS', region_id='S')
        cls.service = Service.objects.create(line_name='11', date='1904-05-05', current=True)
        cls.service.operator.add(cls.operator)
        cls.vehicle = Vehicle(source=source)
        cls.command = Command()
        cls.command.source = source

    def test_get_journey(self):
        item = {
            'journey_id': '1135',
            'vehicle_id': '3032',
            'destination': 'Yoker',
            'service_name': '11'
        }
        journey, created = self.command.get_journey(item)
        self.assertEqual('1135', journey.code)
        self.assertEqual('Yoker', journey.destination)
        self.assertEqual('3032', journey.vehicle.fleet_number)
        self.assertIsNone(journey.vehicle.operator)
        self.assertIsNone(journey.service)
        self.assertTrue(created)

    def test_vehicle_location(self):
        item = {
            'heading': 76,
            'latitude': 55.95376,
            'longitude': -3.18718,
            'journey_id': '1135',
            'vehicle_id': '3032',
            'destination': 'Yoker',
            'service_name': '11'
        }
        location = self.command.create_vehicle_location(item, self.vehicle, self.service)
        self.assertTrue(location.latlong)
        print(self.operator)
        self.assertEqual(self.vehicle.operator, self.operator)

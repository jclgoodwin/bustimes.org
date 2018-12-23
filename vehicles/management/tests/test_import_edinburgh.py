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
        cls.service = Service.objects.create(line_name='corbyn', date='1904-05-05')
        cls.service.operator.add(cls.operator)
        cls.vehicle = Vehicle(source=source)
        cls.command = Command()
        cls.command.source = source

    def test_get_vehicle_and_service(self):
        item = {
            'vehicle_id': 'jeremy',
            'service_name': 'corbyn'
        }
        vehicle, created, service = self.command.get_vehicle_and_service(item)
        self.assertIsNone(vehicle.operator)
        self.assertTrue(created)
        self.assertIsNone(service)

    def test_vehicle_location(self):
        item = {
            'vehicle_id': 'jeremy',
            'latitude': 55.95376,
            'longitude': -3.18718,
            'heading': 76,
            'service_name': 'corbyn'
        }
        location = self.command.create_vehicle_location(item, self.vehicle, self.service)
        self.assertTrue(location.latlong)
        self.assertEqual(self.vehicle.operator, self.operator)

from django.test import TestCase
from busstops.models import DataSource, Region, Operator, Service
from ..commands.import_edinburgh import Command


class EdinburghImportTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        source = DataSource.objects.create(name='TfE', url='', datetime='1066-01-01 12:18Z')
        Region.objects.create(name='Scotland', id='S')
        cls.operator = Operator.objects.create(name='Lothian Buses', id='LOTH', region_id='S')
        cls.service = Service.objects.create(line_name='11', date='1904-05-05', current=True)
        cls.service.operator.add(cls.operator)
        cls.command = Command()
        cls.command.source = source

    def test_get_journey(self):
        item = {
            'journey_id': '1135',
            'vehicle_id': '3032',
            'destination': 'Yoker',
            'service_name': '11',
            'heading': 76,
            'latitude': 55.95376,
            'longitude': -3.18718,
            'last_gps_fix': 1554038242,
        }
        with self.assertNumQueries(15):
            self.command.handle_item(item, None)
        journey = self.command.source.vehiclejourney_set.get()

        self.assertEqual('1135', journey.code)
        self.assertEqual('Yoker', journey.destination)
        self.assertEqual(self.service, journey.service)

        with self.assertNumQueries(1):
            vehicle, created = self.command.get_vehicle(item)
        self.assertEqual(self.operator, vehicle.operator)
        self.assertEqual(3032, vehicle.fleet_number)
        self.assertFalse(created)

    def test_vehicle_location(self):
        item = {
            'heading': 76,
            'latitude': 55.95376,
            'longitude': -3.18718,
            'last_gps_fix': 1554038242,
        }
        location = self.command.create_vehicle_location(item)
        self.assertEqual(76, location.heading)
        self.assertTrue(location.latlong)

        self.assertEqual('2019-03-31 13:17:22+01:00', str(self.command.get_datetime(item)))

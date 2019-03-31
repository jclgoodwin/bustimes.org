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
        }
        with self.assertNumQueries(6):
            journey, created = self.command.get_journey(item)
        self.assertEqual('1135', journey.code)
        self.assertEqual('Yoker', journey.destination)
        self.assertEqual('3032', journey.vehicle.fleet_number)
        self.assertEqual(self.operator, journey.vehicle.operator)
        self.assertEqual(self.service, journey.service)
        self.assertTrue(created)

        with self.assertNumQueries(3):
            journey, created = self.command.get_journey(item)

    def test_vehicle_location(self):
        item = {
            'heading': 76,
            'latitude': 55.95376,
            'longitude': -3.18718,
            'last_gps_fix': 1554036201,
        }
        location = self.command.create_vehicle_location(item)
        self.assertEqual(76, location.heading)
        self.assertEqual('2019-03-31 13:43:21+01:00', str(location.datetime))
        self.assertTrue(location.latlong)

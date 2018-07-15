from django.test import TestCase
from ...models import DataSource, Service, Vehicle, Operator, Region
from ..commands.import_reading import Command


class ReadingImportTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        source = DataSource.objects.create(name='Reading', url='', datetime='1066-01-01 12:18Z')
        Region.objects.create(name='Scotch Land', id='S')

        cls.otis = Operator.objects.create(name="Otis Redding's Buses", id='RBUS', region_id='S')
        cls.kenn = Operator.objects.create(name="Kenny's Coaches", id='KENN', region_id='S')
        cls.thames = Operator.objects.create(name='Thames', id='THVB', region_id='S')
        cls.green = Operator.objects.create(name='Green Line', id='GLRB', region_id='S')

        cls.service = Service.objects.create(line_name='102', date='1904-05-05')
        cls.service.operator.add(cls.otis)

        cls.vehicle = Vehicle(source=source)
        cls.command = Command()
        cls.command.source = source

        cls.item = {
            'vehicle': '751',
            'service': 'k102',
            'observed': '2018-07-13 12:40:07',
            'latitude': '51.443426',
            'longitude': '-0.955788',
            'bearing': '301'
        }

    def test_get_vehicle_and_service(self):
        vehicle, created, service = self.command.get_vehicle_and_service(self.item)
        self.assertEqual(self.otis, vehicle.operator)
        self.assertTrue(created)
        self.assertEqual(self.service, service)

        self.item['service'] = 'TV702'
        vehicle, _, service = self.command.get_vehicle_and_service(self.item)
        self.assertEqual(self.thames, vehicle.operator)
        self.assertIsNone(service)

        self.item['service'] = 'K702'
        vehicle, _, _ = self.command.get_vehicle_and_service(self.item)
        self.assertEqual(self.kenn, vehicle.operator)

        self.item['service'] = ''
        vehicle, _, service = self.command.get_vehicle_and_service(self.item)
        self.assertEqual(self.otis, vehicle.operator)
        self.assertIsNone(service)

        self.item['service'] = '702'
        vehicle, _, _ = self.command.get_vehicle_and_service(self.item)
        self.assertEqual(self.green, vehicle.operator)

    def test_vehicle_location(self):
        location = self.command.create_vehicle_location(self.item, self.vehicle, self.service)
        self.assertTrue(location.latlong)
        self.assertTrue(location.heading)
        self.assertIsNone(location.early)

        location.data = self.item
        self.assertEqual('702', location.get_label())

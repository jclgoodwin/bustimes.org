import vcr
import requests
from mock import patch
from django.test import TestCase
from busstops.models import Service, ServiceCode
from ...models import Vehicle, VehicleLocation, VehicleType
from ..commands import import_hogia


def error():
    raise Exception()


def timeout(*args, **kwargs):
    raise requests.exceptions.Timeout()


class HogiaImportTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        service = Service.objects.create(date='2010-10-10', service_code='18')
        other_service = Service.objects.create(date='2010-10-10', service_code='36')

        ServiceCode.objects.create(scheme='NCC Hogia', service=service, code='231')
        ServiceCode.objects.create(scheme='NCC Hogia', service=other_service, code='240')
        ServiceCode.objects.create(scheme='Idris Elba', service=other_service, code='231')

    def test_handle(self):
        command = import_hogia.Command()

        # handle should call update
        with self.assertRaises(Exception):
            with patch('vehicles.management.commands.import_hogia.Command.update', side_effect=error):
                command.handle()

        # now actually test update
        with vcr.use_cassette('data/hogia.yaml'):
            command.update()

        vehicle = Vehicle.objects.get(code='315_YN03_UVT')

        self.assertEqual(str(vehicle.source), 'NCC Hogia')

        vehicle.vehicle_type = VehicleType.objects.create(name='Bristol VR')
        vehicle.save()

        response = self.client.get(vehicle.get_absolute_url())

        self.assertContains(response, '<h1>315 YN03 UVT</h1>')
        self.assertContains(response, '<p>Bristol VR</p>')

        with self.assertNumQueries(2):
            json = self.client.get('/vehicles.json').json()
        self.assertEqual(len(json['features']), 4)
        self.assertEqual(json['features'][0]['properties']['delta'], -5)
        self.assertEqual(json['features'][0]['properties']['direction'], 114)
        self.assertEqual(json['features'][0]['properties']['service']['url'], '/services/18')

        self.assertEqual(VehicleLocation.objects.count(), 4)
        self.assertEqual(VehicleLocation.objects.filter(current=True).count(), 4)

        # if run again with no changes, shouldn't create any new VehicleLocations
        with vcr.use_cassette('data/hogia.yaml'):
            command.update()
        self.assertEqual(VehicleLocation.objects.count(), 4)
        self.assertEqual(VehicleLocation.objects.filter(current=True).count(), 4)

        # if request times out...
        with patch('vehicles.management.import_live_vehicles.logger') as logger:
            with patch('requests.Session.get', side_effect=timeout):
                command.update()
        self.assertTrue(logger.error.called)
        self.assertEqual(VehicleLocation.objects.filter(current=True).count(), 4)

import vcr
import requests
from mock import patch
from django.test import TestCase
from ...models import Vehicle, VehicleLocation
with patch('time.sleep', return_value=None):
    from ..commands import import_hogia


def error():
    raise Exception()


def timeout(*args, **kwargs):
    raise requests.exceptions.Timeout()


class CorrectOperatorsTest(TestCase):
    @vcr.use_cassette('data/hogia.yaml')
    def test_handle(self):
        command = import_hogia.Command()

        # handle should call update
        with self.assertRaises(Exception):
            with patch('busstops.management.commands.import_hogia.Command.update', side_effect=error):
                command.handle()

        # now actually test update
        command.update()

        vehicle = Vehicle.objects.get(code='315_YN03_UVT')
        response = self.client.get(vehicle.get_absolute_url())

        self.assertContains(response, '<h1>315 YN03 UVT</h1>')

        for journey in vehicle.get_journeys():
            for location in journey:
                self.assertAlmostEqual(location.latlong.x, 1.592503)
                self.assertAlmostEqual(location.latlong.y, 52.69956)

        response = self.client.get('/vehicles')
        self.assertContains(response, 'vehicles.min.js')

        response = self.client.get('/vehicles.json')
        self.assertEqual(len(response.json()['features']), 4)

        self.assertEqual(VehicleLocation.objects.filter(current=True).count(), 4)

        # if request times out, no locations should be 'current'
        with patch('requests.Session.get', side_effect=timeout):
            command.update()
        self.assertEqual(VehicleLocation.objects.filter(current=True).count(), 0)

    def test_vehicle_reg(self):
        vehicle = Vehicle()

        vehicle.code = '_7_-_YJ58_CEY'
        self.assertEqual(vehicle.reg(), 'YJ58CEY')

        vehicle.code = '3990_ME'
        self.assertEqual(vehicle.reg(), '3990ME')

        vehicle.code = '50_-_UWW_2X'
        self.assertEqual(vehicle.reg(), 'UWW2X')

        vehicle.code = '407_YJ59_AYY'
        self.assertEqual(vehicle.reg(), 'YJ59AYY')

        vehicle.code = '116-YN53_CFZ'
        self.assertEqual(vehicle.reg(), 'YN53CFZ')

        vehicle.code = 'MX_53_JVF'
        self.assertEqual(vehicle.reg(), 'MX53JVF')

        vehicle.code = '33824'
        self.assertIsNone(vehicle.reg())

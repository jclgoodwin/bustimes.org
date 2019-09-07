from vcr import use_cassette
from mock import patch
from django.test import TestCase, override_settings
from freezegun import freeze_time
from busstops.models import Region, Operator, DataSource, Service
from ...models import Vehicle, VehicleLocation
from ..commands import import_live_ziptrip


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class ZipTripTest(TestCase):
    def setUp(self):
        Region.objects.create(id='EA')
        Operator.objects.create(id='LYNX', region_id='EA')
        Operator.objects.create(id='CBUS', region_id='EA')
        Operator.objects.create(id='GAHL', region_id='EA', slug='go-ahead-lichtenstein')
        Operator.objects.create(id='LGEN', region_id='EA')
        Operator.objects.create(id='IPSW', region_id='EA')
        self.service = Service.objects.create(line_name='7777', date='2010-01-01', service_code='007', slug='foo-foo')
        self.service.operator.set(['LYNX'])

        now = '2018-08-06T22:41:15+01:00'
        self.source = DataSource.objects.create(datetime=now)
        self.vehicle = Vehicle.objects.create(code='203', operator_id='CBUS', source=self.source)

    def test_handle(self):
        command = import_live_ziptrip.Command()
        command.source = self.source

        item = {
            "vehicleCode": "LYNX__2_-_YJ55_BJE",
            "routeName": "7777",
            "position": {
                "latitude": 52.731614,
                "longitude": 0.385742
            },
            "reported": "2018-08-31T21:30:04+00:00",
            "received": "2018-08-31T21:30:15.8465176+00:00",
            "bearing": -24,
        }

        command.handle_item(item, self.source.datetime)

        location = VehicleLocation.objects.get()

        self.assertEqual(336, location.heading)
        self.assertNotEqual(self.vehicle, location.journey.vehicle)
        self.assertEqual('LYNX', location.journey.vehicle.operator_id)
        self.assertEqual(self.service, location.journey.service)

        self.service.operator.set(['LGEN'])

        item['vehicleCode'] = 'LAS_203'
        # Although a vehicle called '203' exists, it belongs to a different operator, so a new one should be created
        command.handle_item(item, self.source.datetime)
        location = VehicleLocation.objects.last()
        self.assertEqual('GAHL', location.journey.vehicle.operator_id)
        self.assertNotEqual(self.vehicle, location.journey.vehicle)
        self.assertEqual(self.service, location.journey.service)

        self.assertEqual(3, Vehicle.objects.count())

        with self.assertNumQueries(1):
            with freeze_time('2018-08-31T21:35:04+00:00'):
                response = self.client.get('/vehicles.json?service=007').json()
        self.assertEqual(2, len(response['features']))

        with self.assertNumQueries(1):
            with freeze_time('2018-08-31T22:55:04+00:00'):
                response = self.client.get('/vehicles.json?service=007').json()
        self.assertEqual(0, len(response['features']))

        self.service.operator.set(['LGEN', 'GAHL'])

        response = self.client.get('/operators/go-ahead-lichtenstein')
        self.assertContains(response, 'fleet list')
        self.assertContains(response, '/operators/go-ahead-lichtenstein/vehicles')

        with self.assertNumQueries(3):
            response = self.client.get('/operators/go-ahead-lichtenstein/vehicles')
        self.assertContains(response, '7777')
        self.assertContains(response, '203')
        # last seen some days ago
        self.assertContains(response, '31 August 2018 22:30')

        with freeze_time('31 August 2018'):
            response = self.client.get('/operators/go-ahead-lichtenstein/vehicles')
        # last seen today - should only show time
        self.assertNotContains(response, '31 August 2018')
        self.assertContains(response, '22:30')

        with self.assertNumQueries(2):
            response = self.client.get(self.vehicle.get_absolute_url())
        self.assertEqual(response.status_code, 200)

        # service vehicle history
        with self.assertNumQueries(5):
            response = self.client.get('/services/foo-foo/vehicles?date=poop')
        self.assertContains(response, 'Vehicles')
        self.assertContains(response, '/vehicles/')
        self.assertContains(response, 'value="2018-08-31"')

        with self.assertNumQueries(4):
            response = self.client.get('/services/foo-foo/vehicles?date=2004-04-04')
        self.assertNotContains(response, 'table>')

    @patch('vehicles.management.commands.import_live_ziptrip.sleep')
    def test_get_itmes(self, sleep):
        command = import_live_ziptrip.Command()
        with use_cassette('data/vcr/ziptrip.yaml'):
            with freeze_time('Thu, 04 Jul 2019 17:51:53 GMT'):
                items = list(command.get_items())
        self.assertEqual(26, len(items))
        self.assertTrue(sleep.called)

    def test_unknown_operator(self):
        command = import_live_ziptrip.Command()
        command.source = self.source

        item = {
            "vehicleCode": "GHA_DA04_GHA",
            "position": {
                "latitude": 0,
                "longitude": 0
            },
            "reported": "2018-08-31T21:30:04+00:00",
            "received": "2018-08-31T21:30:15.8465176+00:00",
            "bearing": -24,
        }
        command.handle_item(item, self.source.datetime)
        self.assertFalse(VehicleLocation.objects.all())

    def test_fleet_number(self):
        command = import_live_ziptrip.Command()
        command.source = self.source

        item = {
            "vehicleCode": "IPSW_91_-_YJ12_GWF",
            "position": {
                "latitude": 0,
                "longitude": 0
            },
            "reported": "2018-08-31T21:30:04+00:00",
            "received": "2018-08-31T21:30:15.8465176+00:00",
            "bearing": -24,
        }
        command.handle_item(item, self.source.datetime)
        vehicle = Vehicle.objects.get(code='91_-_YJ12_GWF')
        self.assertEqual(vehicle.fleet_number, 91)
        self.assertEqual(vehicle.reg, '')

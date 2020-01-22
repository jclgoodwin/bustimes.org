import vcr
from mock import patch
from freezegun import freeze_time
from django.test import TestCase
from django.utils import timezone
from busstops.models import DataSource, Region, Operator, Service, StopPoint
from bustimes.models import Route, Trip, Calendar
from ..commands.import_go_ahead import Command
from ...models import VehicleLocation


@freeze_time('2019-03-17T16:17:49.000Z')
class GoAheadImportTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        source = DataSource.objects.create(name='Go Ahead', datetime=timezone.now())
        cls.command = Command()
        cls.command.source = source
        cls.command.opcos = {
            'eastangliabuses': ('KCTB',)
        }

        Region.objects.create(name='East Anglia', id='EA')
        cls.operator = Operator.objects.create(name='Go East', id='KCTB', region_id='EA')
        cls.service = Service.objects.create(line_name='501', date='2019-03-17', current=True,
                                             geometry='MULTILINESTRING((1.3 52.6, 1.3 52.6))')
        cls.service.operator.add(cls.operator)

        stop = StopPoint.objects.create(latlong='POINT(1.3 52.6)', locality_centre=False, active=True)
        route = Route.objects.create(service=cls.service, source=source)
        calendar = Calendar.objects.create(mon=True, tue=True, wed=True, thu=True, fri=True, sat=True, sun=True,
                                           start_date='2019-03-17')
        Trip.objects.create(calendar=calendar, route=route, destination=stop, start='16:10', end='16:20')

    @patch('vehicles.management.commands.import_go_ahead.sleep')
    def test_get_items(self, sleep):
        with vcr.use_cassette('data/vcr/go_ahead.yaml'):
            with self.assertNumQueries(2):
                items = list(self.command.get_items())
        self.assertEqual(len(items), 3)
        self.assertTrue(sleep.called)

    def test_handle_item(self):
        item = {
            "ref": "R09FQS02Mjh8NTMx",
            "vehicleRef": "GOEA-628",
            "datedVehicleJourney": 531,
            "geo": {
                "distance": 1.69,
                "longitude": 1.2934628,
                "latitude": 52.6241455,
                "bearing": None
            },
            "lineRef": "501",
            "direction": "inbound",
            "destination": {
                "name": "Castle Meadow",
                "ref": "2900N12108"
            },
            "vehicleMake": "",
            "stopProgress": 0,
            "recordedTime": "2019-03-31T12:24:54.000Z",
            "updatedAtUTC": "2019-03-31T11:25:05.000Z"
        }
        with self.assertNumQueries(12):
            self.command.handle_item(item, self.command.source.datetime)
        with self.assertNumQueries(1):
            self.command.handle_item(item, self.command.source.datetime)

        location = VehicleLocation.objects.get()
        self.assertEqual('2019-03-31 11:24:54+00:00', str(location.datetime))
        self.assertIsNone(location.heading)

        item['recordedTime'] = '2019-03-31T12:30:00.000Z'
        item['geo']['longitude'] = 0
        with self.assertNumQueries(3):
            self.command.handle_item(item, self.command.source.datetime)

        location = VehicleLocation.objects.last()
        self.assertEqual(270, location.heading)

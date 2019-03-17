import vcr
from freezegun import freeze_time
from django.test import TestCase
from django.utils import timezone
from busstops.models import DataSource, Region, Operator, Service, StopPoint, StopUsage, Journey, StopUsageUsage
from ..commands.import_go_ahead import Command
from ...models import VehicleLocation


@freeze_time('2019-03-17T16:17:49.000Z')
class GoAheadImportTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        source = DataSource.objects.create(name='TfE', datetime=timezone.now())
        cls.command = Command()
        cls.command.source = source
        cls.command.opcos = {
            'eastangliabuses': ('KCTB',)
        }

        Region.objects.create(name='East Anglia', id='EA')
        cls.operator = Operator.objects.create(name='Go East', id='KCTB', region_id='EA')
        cls.service = Service.objects.create(line_name='501', date='2019-03-17', current=True)
        cls.service.operator.add(cls.operator)

        stop = StopPoint.objects.create(latlong='POINT(1.3 52.6)', locality_centre=False, active=True)
        StopUsage.objects.create(stop=stop, order=1, service=cls.service)
        journey = Journey.objects.create(datetime=source.datetime, destination_id=stop, service=cls.service)
        StopUsageUsage.objects.create(journey=journey, datetime=source.datetime, order=1, stop=stop)

    def test_get_items(self):
        with vcr.use_cassette('data/vcr/go_ahead.yaml'):
            items = list(self.command.get_items())

        self.assertEqual(len(items), 3)

    def test_handle_item(self):
        item = {
            "ref": "R09FQS02Mjh8NTMx",
            "vehicleRef": "GOEA-628",
            "datedVehicleJourney": 531,
            "geo": {
                "distance": 1.69,
                "longitude": 1.2934628,
                "latitude": 52.6241455,
                "bearing": 0
            },
            "lineRef": "501",
            "direction": "inbound",
            "destination": {
                "name": "Castle Meadow",
                "ref": "2900N12108"
            },
            "vehicleMake": "",
            "stopProgress": 0,
            "recordedTime": "2019-03-17T14:27:17.000Z",
            "updatedAtUTC": "2019-03-17T14:27:25.000Z"
        }
        self.command.handle_item(item, self.command.source.datetime)
        self.command.handle_item(item, self.command.source.datetime)

        self.assertEqual(VehicleLocation.objects.count(), 1)

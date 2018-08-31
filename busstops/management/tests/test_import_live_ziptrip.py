from django.test import TestCase
from ...models import Region, Operator, DataSource, VehicleLocation
from ..commands import import_live_ziptrip


class ZipTripTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Region.objects.create(id='EA')
        Operator.objects.create(id='LYNX', region_id='EA')
        now = '2018-08-06T22:41:15+01:00'
        cls.source = DataSource.objects.create(datetime=now)

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

        self.assertEquals(336, location.heading)
        self.assertEquals('LYNX', location.vehicle.operator_id)

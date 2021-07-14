from django.test import TestCase
from busstops.models import DataSource, Region, Operator
from ...models import Vehicle
from ...utils import flush_redis
from ..commands.newport import Command


class MegabusTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        DataSource.objects.create(name="newport")
        cls.command = Command()
        cls.command.do_source()

        region = Region.objects.create(id="W", name="Wales")
        Operator.objects.create(id="NWPT", name="Newport Bus", region=region)

    def test_handle_item(self):
        flush_redis()

        item = {
            'vehicleRef': '352',
            'routeName': 'T7',
            'scheduledTripStartTime': '2021-07-14T19:00:00+01:00',
            'destination': 'Queens Hills',
            'position': {'bearing': 302.12, 'latitude': 51.24, 'longitude': -2.655534},
            'reported': '2021-07-14T18:52:43+00:00',
        }

        self.command.handle_item(item)
        self.command.save()

        vehicle = Vehicle.objects.get()
        self.assertEqual('352', str(vehicle))

        self.assertEqual('14 Jul 2021 18:52:43', str(vehicle.latest_location))
        self.assertEqual('14 Jul 21 18:00 T7 1900  to Queens Hills', str(vehicle.latest_journey))
        self.assertIsNotNone(vehicle.latest_journey.data)

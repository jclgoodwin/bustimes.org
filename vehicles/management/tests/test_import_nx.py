from mock import patch
from freezegun import freeze_time
from django.test import TestCase
from django.utils import timezone
from busstops.models import DataSource, Region, Operator
from ...models import Vehicle
from ..commands.import_aircoach import Command as AircoachCommand, NatExpCommand
from ..commands.import_kings_ferry import Command as KingsFerryCommand


@freeze_time("2019-11-17T16:17:49.000Z")
class NatExpTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        source = DataSource.objects.create(
            name="Nathaniel Express", datetime=timezone.now()
        )
        cls.aircoach_command = AircoachCommand()
        cls.aircoach_command.source = source
        cls.kings_ferry_command = KingsFerryCommand()
        cls.kings_ferry_command.source = source
        cls.nat_exp_command = NatExpCommand()
        cls.nat_exp_command.source = source

        gb = Region.objects.create(id="GB")
        Operator.objects.create(id="NATX", name="Nathaniel Express", region=gb)

    @patch("vehicles.management.commands.import_nx.sleep")
    def test_get_items(self, sleep):
        with self.assertNumQueries(1):
            items = list(self.aircoach_command.get_items())
            self.assertEqual(len(items), 0)

        with self.assertNumQueries(1):
            items = list(self.nat_exp_command.get_items())
            self.assertEqual(len(items), 0)

        with self.assertNumQueries(1):
            items = list(self.kings_ferry_command.get_items())
            self.assertEqual(len(items), 0)

        self.assertFalse(sleep.called)

    def test_handle_item(self):
        items = [
            {
                "date": "2020-07-16",
                "linkDate": "16-07-2020",
                "startTime": {
                    "dateTime": "2020-07-16 09:30:00",
                    "hrs": 9,
                    "mins": 30,
                    "time": "09:30",
                },
                "route": "491",
                "dir": "O",
                "journeyId": "HA",
                "reference": None,
                "linkName": "London-Great_Yarmouth",
                "duration": {"hrs": 4, "mins": 0, "time": "04:00"},
                "multiDay": False,
                "depart": "London",
                "arrival": "Norwich",
                "live": {
                    "vehicleId": "342818",
                    "vehicle": "BV69 KSK",
                    "lat": 52.624013,
                    "lon": 1.293241,
                    "bearing": 217,
                    "status": "1",
                    "timestamp": {
                        "dateTime": "2020-07-16 13:09:43",
                        "hrs": 13,
                        "mins": 9,
                        "time": "13:09",
                    },
                    "timeZone": "BST",
                    "geoLocation": "Cannock Road, Norwich, Norfolk",
                    "gpsProvider": "Traffilog",
                },
                "duplicateCount": None,
                "dups": None,
                "started": None,
                "next": {
                    "date": "2020-07-16",
                    "linkDate": "16-07-2020",
                    "journeyId": "HC",
                },
                "prev": None,
            },
            {
                "date": "2020-07-16",
                "linkDate": "16-07-2020",
                "startTime": {
                    "dateTime": "2020-07-16 13:00:00",
                    "hrs": 13,
                    "mins": 0,
                    "time": "13:00",
                },
                "route": "491",
                "dir": "O",
                "journeyId": "HC",
                "reference": None,
                "linkName": "London-Great_Yarmouth",
                "duration": {"hrs": 4, "mins": 15, "time": "04:15"},
                "multiDay": False,
                "depart": "London",
                "arrival": "Great Yarmouth",
                "live": {
                    "vehicleId": "342752",
                    "vehicle": "BV69 KPT",
                    "lat": 51.916845,
                    "lon": 0.218966,
                    "bearing": 356,
                    "status": "1",
                    "timestamp": {
                        "dateTime": "2020-07-16 14:45:52",
                        "hrs": 14,
                        "mins": 45,
                        "time": "14:45",
                    },
                    "timeZone": "BST",
                    "geoLocation": "M11, Uttlesford, Essex",
                    "gpsProvider": "Traffilog",
                },
                "duplicateCount": None,
                "dups": None,
                "started": None,
                "next": None,
                "prev": {
                    "date": "2020-07-16",
                    "linkDate": "16-07-2020",
                    "journeyId": "HA",
                },
            },
        ]

        with patch(
            "vehicles.management.commands.import_nx.Command.get_items",
            return_value=items,
        ):
            self.nat_exp_command.update()

        self.assertEqual(2, Vehicle.objects.all().count())

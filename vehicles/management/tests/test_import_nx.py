from unittest.mock import patch
import time_machine
from django.test import TestCase
from django.utils import timezone
from busstops.models import DataSource, Region, Operator
from ...models import Vehicle
from ..commands.import_nx import parse_datetime
from ..commands.import_aircoach import Command as AircoachCommand, NatExpCommand


@time_machine.travel("2019-11-17T16:17:49.000Z")
class NatExpTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        source = DataSource.objects.create(
            name="Nathaniel Express", datetime=timezone.now()
        )
        cls.aircoach_command = AircoachCommand()
        cls.aircoach_command.source = source
        cls.nat_exp_command = NatExpCommand()
        cls.nat_exp_command.source = source

        gb = Region.objects.create(id="GB")
        Operator.objects.create(id="NATX", name="Nathaniel Express", region=gb)

    def test_parse_datetime(self):
        self.assertEqual(str(parse_datetime("2021-10-31 00:00:00")), "2021-10-31 00:00:00+01:00")
        self.assertEqual(str(parse_datetime("2021-10-31 01:05:00")), "2021-10-31 01:05:00+01:00")  # ambiguous time
        self.assertEqual(str(parse_datetime("2021-10-31 02:05:00")), "2021-10-31 02:05:00+00:00")

        self.assertEqual(str(parse_datetime("2021-03-28 00:00:00")), "2021-03-28 00:00:00+00:00")
        self.assertEqual(str(parse_datetime("2021-03-28 01:05:00")), "2021-03-28 01:05:00+00:00")  # non existent time
        self.assertEqual(str(parse_datetime("2021-03-28 02:05:00")), "2021-03-28 02:05:00+01:00")

    @patch("vehicles.management.commands.import_nx.sleep")
    def test_get_items(self, sleep):
        with self.assertNumQueries(1):
            items = list(self.aircoach_command.get_items())
            self.assertEqual(len(items), 0)

        with self.assertNumQueries(1):
            items = list(self.nat_exp_command.get_items())
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
                "timetables": [],
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
                "timetables": [
                    {
                        "arrive": {
                            "dateTime": "2022-04-07 01:55:00",
                            "hrs": 1,
                            "mins": 55,
                            "time": "01:55"
                        },
                        "depart": {
                            "dateTime": "2022-04-07 02:00:00",
                            "hrs": 2,
                            "mins": 0,
                            "time": "02:00"
                        },
                        "layover": 5,
                        "timingPoint": 0,
                        "fareStage": 0,
                        "distance": 0,
                        "status": None,
                        "timeZone": "BST",
                        "actualStatus": -1,
                        "duplicateCount": 0,
                        "delayed": False,
                        "eta": {
                            "etaArrive": {
                                "dateTime": "2022-04-07 02:02:58",
                                "hrs": 2,
                                "mins": 2,
                                "time": "02:02"
                            },
                            "etaDepart": {
                                "dateTime": "2022-04-07 02:03:58",
                                "hrs": 2,
                                "mins": 3,
                                "time": "02:03"
                            },
                            "etaLayover": 1,
                            "arrive": {
                                "dateTime": "2022-04-07 02:02:58",
                                "hrs": 2,
                                "mins": 2,
                                "time": "02:02"
                            },
                            "depart": {
                                "dateTime": "2022-04-07 02:04:12",
                                "hrs": 2,
                                "mins": 4,
                                "time": "02:04"
                            },
                            "atStop": False,
                            "late": False,
                            "status": "visited",
                            "timestamp": "2022-04-07 02:02:58 +0000",
                            "gate": None
                        },
                        "stopActivity": None
                    },
                    None,
                    {
                        "arrive": {
                            "dateTime": "2022-04-07 02:28:00",
                            "hrs": 2,
                            "mins": 28,
                            "time": "02:28"
                        },
                        "depart": {
                            "dateTime": "2022-04-07 02:28:00",
                            "hrs": 2,
                            "mins": 28,
                            "time": "02:28"
                        },
                        "layover": 0,
                        "timingPoint": 0,
                        "fareStage": 0,
                        "distance": 0,
                        "status": None,
                        "timeZone": "BST",
                        "actualStatus": -1,
                        "duplicateCount": 0,
                        "delayed": False,
                        "eta": {
                            "etaArrive": {
                                "dateTime": "2022-04-07 02:34:00",
                                "hrs": 2,
                                "mins": 34,
                                "time": "02:34"
                            },
                            "etaDepart": {
                                "dateTime": "2022-04-07 02:34:00",
                                "hrs": 2,
                                "mins": 34,
                                "time": "02:34"
                            },
                            "etaLayover": 0,
                            "arrive": None,
                            "depart": None,
                            "atStop": False,
                            "late": False,
                            "status": "next_stop",
                            "timestamp": "2022-04-07 02:16:10 +0000",
                            "gate": None
                        },
                        "stopActivity": None
                    },
                    {
                        "arrive": {
                            "dateTime": "2022-04-07 02:30:00",
                            "hrs": 2,
                            "mins": 30,
                            "time": "02:30"
                        },
                        "depart": {
                            "dateTime": "2022-04-07 02:30:00",
                            "hrs": 2,
                            "mins": 30,
                            "time": "02:30"
                        },
                        "layover": 0,
                        "timingPoint": 0,
                        "fareStage": 0,
                        "distance": 0,
                        "status": None,
                        "timeZone": "BST",
                        "actualStatus": -1,
                        "duplicateCount": 0,
                        "delayed": False,
                        "eta": {
                            "etaArrive": {
                                "dateTime": "2022-04-07 02:36:00",
                                "hrs": 2,
                                "mins": 36,
                                "time": "02:36"
                            },
                            "etaDepart": {
                                "dateTime": "2022-04-07 02:36:00",
                                "hrs": 2,
                                "mins": 36,
                                "time": "02:36"
                            },
                            "etaLayover": 0,
                            "arrive": None,
                            "depart": None,
                            "atStop": False,
                            "late": False,
                            "status": "future",
                            "timestamp": "2022-04-07 02:16:10 +0000",
                            "gate": None
                        },
                        "stopActivity": None
                    },
                ],
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
        ) as get_items:
            self.nat_exp_command.update()
        get_items.assert_called()

        response = self.client.get('/vehicles.json').json()
        self.assertEqual(response[0]['destination'], 'Great Yarmouth')
        self.assertEqual(response[0]['delay'], 360.0)

        self.assertEqual(2, Vehicle.objects.all().count())

from pathlib import Path
from unittest import mock

import fakeredis
import vcr
from django.test import TestCase
from django.core.management import call_command
from django.db import IntegrityError

from busstops.models import DataSource, Operator, Service
from ..commands.import_first import Command
from ...models import VehicleJourney


class FirstTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.source = DataSource.objects.create(
            name="First", url="https://example.com/socket_information"
        )
        o = Operator.objects.create(noc="BDGR", name="Badgerline")
        s = Service.objects.create(
            current=True,
            geometry="POLYGON ((1.2 52.6, 1.2 52.7, 1.3 52.7, 1.3 52.6, 1.2 52.6))",
        )
        s.operator.add(o)

    def test_sock_it(self):
        with (
            vcr.use_cassette(
                str(Path(__file__).resolve().parent / "vcr" / "first.yaml")
            ),
            mock.patch(
                "vehicles.management.commands.import_first.connect"
            ) as websocket_connect,
            self.assertNumQueries(3),
            self.assertRaises(IntegrityError),
        ):
            websocket_connect.return_value.__aenter__.return_value.recv.side_effect = [
                "",
                """{"member": [{
                    "dir": "outbound",
                    "line": "B",
                    "status": {
                        "bearing": 61,
                        "location": {
                        "type": "Point",
                            "coordinates": [1.267833, 52.614746]
                        },
                        "vehicle_id": "BDGR-outbound-2025-09-21-0615-11111-B",
                        "recorded_at_time": "2025-09-21T07:02:17+01:00"
                    },
                    "operator": "BDGR",
                    "line_name": "B",
                    "description": "",
                    "operator_name": "Badgerline"
                }]}""",
            ]

            call_command("import_first", "BDGR")

        self.assertEqual(VehicleJourney.objects.count(), 0)

    async def test_handle_data(self):
        cmd = Command()
        cmd.source = self.source
        cmd.cache = {}
        cmd.to_save = []

        redis_client = fakeredis.FakeStrictRedis(version=7)

        with mock.patch(
            "vehicles.management.import_live_vehicles.redis_client", redis_client
        ):
            await cmd.handle_data(
                {
                    "member": [
                        {
                            "dir": "outbound",
                            "line": "B",
                            "status": {
                                "bearing": 61,
                                "location": {
                                    "type": "Point",
                                    "coordinates": [1.267833, 52.614746],
                                },
                                "vehicle_id": "BDGR-outbound-2025-09-21-0615-11111-B",
                                "recorded_at_time": "2025-09-21T07:02:17+01:00",
                            },
                            "stops": [
                                {
                                    "date": "2025-09-21",
                                    "time": "06:15",
                                    "locality": "Woody Knoll",
                                    "atcocode": "",
                                }
                            ],
                            "operator": "BDGR",
                            "line_name": "B",
                            "description": "",
                            "operator_name": "Badgerline",
                        }
                    ]
                }
            )

        v = await VehicleJourney.objects.aget()
        self.assertEqual(v.route_name, "B")
        self.assertEqual(v.code, "0615")

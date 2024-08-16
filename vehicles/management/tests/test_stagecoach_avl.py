from pathlib import Path
from unittest.mock import patch

import fakeredis
import time_machine
import vcr
from django.test import TestCase

from busstops.models import DataSource, Operator, Region, Service

from ...models import VehicleJourney
from ..commands.import_stagecoach_avl import Command


@time_machine.travel("2019-11-17T04:32:00.000Z")
class StagecoachTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.source = DataSource.objects.create(
            name="Stagecoach",
            url="https://api.stagecoach-technology.net/vehicle-tracking/v1/vehicles?services=:*:::",
        )

        r = Region.objects.create(pk="SE")
        o = Operator.objects.create(
            pk="SCOX", name="Oxford", parent="Stagecoach", vehicle_mode="bus", region=r
        )
        s = Service.objects.create(
            line_name="Oxford Tube",
            geometry="MULTILINESTRING((-0.1475818977 51.4928233539,-0.1460401487 51.496737716))",
        )
        s.operator.add(o)

    @patch(
        "vehicles.management.import_live_vehicles.redis_client",
        fakeredis.FakeStrictRedis(version=7),
    )
    def test_handle(self):
        command = Command()
        command.do_source()
        command.operator_codes = ["SDVN"]

        with vcr.use_cassette(
            str(Path(__file__).resolve().parent / "vcr" / "stagecoach_vehicles.yaml")
        ) as cassette:
            with self.assertNumQueries(54):
                command.update()

            cassette.rewind()
            del command.previous_locations["19617"]
            del command.previous_locations["50275"]

            with self.assertNumQueries(2):
                command.update()

        self.assertEqual(
            command.operators,
            {
                "SCOX": Operator(noc="SCOX"),
            },
        )
        self.assertEqual(VehicleJourney.objects.count(), 8)

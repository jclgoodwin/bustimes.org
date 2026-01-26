from pathlib import Path
from unittest.mock import patch

import fakeredis
import time_machine
import vcr
from django.test import TestCase

from busstops.models import DataSource, Operator, OperatorGroup, Region, Service

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

        group = OperatorGroup.objects.create(name="Stagecoach", slug="stagecoach")
        region = Region.objects.create(pk="SE")
        operator = Operator.objects.create(
            pk="SCOX", name="Oxford", vehicle_mode="bus", region=region, group=group
        )
        service = Service.objects.create(
            line_name="Oxford Tube",
            geometry="MULTILINESTRING((-0.1475818977 51.4928233539,-0.1460401487 51.496737716))",
        )
        service.operator.add(operator)

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
            with self.assertNumQueries(79):
                command.update()

            cassette.rewind()
            # make it think 2 vehicles have moved
            del command.identifiers["SCCM:CA:19617"]
            del command.identifiers["SCOX:SOX:50275"]
            with self.assertNumQueries(2):
                command.update()

        self.assertEqual(
            command.operators,
            {
                "SCOX": Operator(noc="SCOX"),
            },
        )
        self.assertEqual(VehicleJourney.objects.count(), 8)

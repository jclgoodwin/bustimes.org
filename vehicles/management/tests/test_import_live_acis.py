import os
from unittest.mock import patch

import fakeredis
from django.test import TestCase
from vcr import use_cassette

from busstops.models import DataSource, Operator, Region

from ...models import VehicleJourney
from ..commands import import_live_acis

DIR = os.path.dirname(os.path.abspath(__file__))


class ACISImportTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Region.objects.create(id="NI")
        Operator.objects.bulk_create(
            [
                Operator(noc="MET", region_id="NI"),
                Operator(noc="GDR", region_id="NI"),
                Operator(noc="ULB", region_id="NI"),
            ]
        )

    @patch("vehicles.management.commands.import_live_acis.sleep")
    @patch("vehicles.management.commands.import_live_acis.Command.get_points")
    @patch(
        "vehicles.management.import_live_vehicles.redis_client",
        fakeredis.FakeStrictRedis(version=7),
    )
    def test_handle(self, get_points, sleep):
        get_points.return_value = ((None, None), (54.5957, -5.9169))

        command = import_live_acis.Command()
        command.do_source()

        with use_cassette(
            os.path.join(DIR, "vcr", "import_live_acis.yaml"), match_on=["body"]
        ):
            with patch("builtins.print") as mocked_print:
                command.update()
        mocked_print.assert_called()

        # Should only create 18 items - two are duplicates
        self.assertEqual(18, VehicleJourney.objects.count())

        with use_cassette(
            os.path.join(DIR, "vcr", "import_live_acis.yaml"), match_on=["body"]
        ):
            command.update()

        # Should create no new items - no changes
        self.assertEqual(18, VehicleJourney.objects.count())

    def test_get_items(self):
        command = import_live_acis.Command()
        command.source = DataSource()
        self.assertEqual([], list(command.get_items()))

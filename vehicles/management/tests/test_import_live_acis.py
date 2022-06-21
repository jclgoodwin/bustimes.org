import os
from unittest.mock import patch
from vcr import use_cassette
from django.test import TestCase
from busstops.models import Region, Operator, DataSource
from ...models import VehicleJourney
from ..commands import import_live_acis


DIR = os.path.dirname(os.path.abspath(__file__))


class ACISImportTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Region.objects.create(id="NI")
        Operator.objects.bulk_create(
            [
                Operator(id="MET", region_id="NI"),
                Operator(id="GDR", region_id="NI"),
                Operator(id="ULB", region_id="NI"),
            ]
        )

    @patch("vehicles.management.commands.import_live_acis.sleep")
    @patch("vehicles.management.commands.import_live_acis.Command.get_points")
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
        self.assertEqual(18, VehicleJourney.objects.all().count())

        with use_cassette(
            os.path.join(DIR, "vcr", "import_live_acis.yaml"), match_on=["body"]
        ):
            command.update()

        # Should create no new items - no changes
        self.assertEqual(18, VehicleJourney.objects.all().count())

    def test_get_items(self):
        command = import_live_acis.Command()
        command.source = DataSource()
        self.assertEqual([], list(command.get_items()))

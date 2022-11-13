from pathlib import Path

import vcr
from django.core.management import call_command
from django.test import TestCase, override_settings

from ...models import Region


class ImportOperatorsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Region.objects.create(id="GB", name="Great Britain")
        Region.objects.create(id="S", name="Scotland")
        Region.objects.create(id="W", name="Wales")
        Region.objects.create(id="WM", name="West Midlands")
        Region.objects.create(id="SW", name="South West")
        Region.objects.create(id="SE", name="South East")
        Region.objects.create(id="EM", name="East Midlands")
        Region.objects.create(id="NE", name="North East")
        Region.objects.create(id="NW", name="North West")
        Region.objects.create(id="EA", name="East Anglia")
        Region.objects.create(id="Y", name="Yorkshire")

    def test_import_noc(self):

        FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

        with override_settings(DATA_DIR=FIXTURES_DIR):
            with vcr.use_cassette(str(FIXTURES_DIR / "noc.yaml")):
                call_command("import_noc")

    # def test_operator_id(self):
    #     """Is a strange NOC code (with an equals sign) correctly handled?"""
    #     self.assertEqual(self.c2c.noc, "CC")
    #     self.assertEqual(self.c2c.name, "c2c")

    # def test_operator_region(self):
    #     # Is the 'SC' region correctly identified as 'S' (Scotland)?
    #     self.assertEqual(self.first_aberdeen.region, self.scotland)

    #     # Is the 'Admin' region correctly identified as 'GB'?
    #     self.assertEqual(self.c2c.region, self.great_britain)

    # def test_operator_name(self):
    #     """Is an uninformative OperatorPublicName like 'First' ignored in
    #     favour of the OperatorReferenceName?
    #     """
    #     self.assertEqual(self.first_aberdeen.name, "First in Aberdeen")
    #     self.assertEqual(self.c2c.name, "c2c")
    #     self.assertEqual(self.weardale.name, "Weardale Community Transport")
    #     self.assertEqual(self.catch22bus.name, "Catch22Bus Ltd")

    #     command = import_operators.Command()

    #     self.assertEqual(
    #         command.get_name(
    #             {
    #                 "OperatorPublicName": "Oakwood Travel",
    #                 "RefNm": "",
    #                 "OpNm": "Catch22Bus Ltd",
    #             }
    #         ),
    #         "Catch22Bus Ltd",
    #     )
    #     self.assertEqual(
    #         command.get_name(
    #             {"OperatorPublicName": "", "RefNm": "", "OpNm": "Loaches Coaches"}
    #         ),
    #         "Loaches Coaches",
    #     )

    # def test_operator_mode(self):
    #     """Is an operator mode like 'DRT' expanded correctly to 'demand responsive transport'?"""
    #     self.assertEqual(self.ace_travel.vehicle_mode, "demand responsive transport")
    #     self.assertEqual(self.ace_travel.get_a_mode(), "A demand responsive transport")
    #     self.assertEqual(self.c2c.get_a_mode(), "A rail")
    #     self.assertEqual(self.first_aberdeen.get_a_mode(), "A bus")
    #     self.assertEqual(self.weardale.get_a_mode(), "A community transport")

    # @skip
    # def test_operator_ignore(self):
    #     """Were some rows correctly ignored?"""
    #     self.assertFalse(len(Operator.objects.filter(noc="TVSR")))

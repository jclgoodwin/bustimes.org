from pathlib import Path
from unittest.mock import patch

import vcr
from django.core.management import call_command
from django.test import TestCase

from vosa.models import Licence

from ...models import DataSource, Operator, Region


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
        Region.objects.create(id="L", name="London")

        # Operator.objects.create(noc="A1CS", name="A1 Coaches")
        # Operator.objects.create(noc="AMSY", name="Arriva North West")
        Operator.objects.create(noc="ANWE", name="Arriva North West")
        # Operator.objects.create(noc="AMAN", name="Arriva North West")
        # Operator.objects.create(noc="AMID", name="Arriva Midlands")
        # Operator.objects.create(noc="AFCL", name="Arriva Midlands")

        Licence.objects.create(
            licence_number="PB0000582",
            discs=0,
            authorised_discs=0,
        )  # Arriva Yorkshire

    def test_import_noc(self):
        FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

        mock_overrides = {
            "WRAY": {"url": "https://www.arrivabus.co.uk/yorkshire"},
            "FCWL": {"twitter": "by_Kernow"},
            "FCYM": {"name": "First Cymru"},
            "AMSY": {"name": "Arriva Merseyside"},
        }

        with vcr.use_cassette(str(FIXTURES_DIR / "noc.yaml")) as cassette, patch(
            "busstops.management.commands.import_noc.yaml.safe_load",
            return_value=mock_overrides,
        ):
            with self.assertNumQueries(3510):
                call_command("import_noc")

            cassette.rewind()

            with self.assertNumQueries(14):
                call_command("import_noc")

            cassette.rewind()

            DataSource.objects.update(datetime=None)

            Licence.objects.create(
                licence_number="PH0004983",
                discs=0,
                authorised_discs=0,
            )  # First Kernow

            with self.assertNumQueries(21):
                call_command("import_noc")

        self.assertEqual(Operator.objects.count(), 3105)

        c2c = Operator.objects.get(noc="CC")
        self.assertEqual(c2c.name, "c2c")
        self.assertEqual(c2c.region_id, "GB")
        self.assertEqual(c2c.vehicle_mode, "rail")

        aact = Operator.objects.get(noc="AACT")
        self.assertEqual(aact.region_id, "Y")
        self.assertEqual(aact.vehicle_mode, "bus")

        actr = Operator.objects.get(noc="ACTR")
        self.assertEqual(actr.vehicle_mode, "demand responsive transport")

        wray = Operator.objects.get(noc="WRAY")
        self.assertEqual(wray.url, "https://www.arrivabus.co.uk/yorkshire")
        self.assertEqual(wray.twitter, "arrivayorkshire")

        kernow = Operator.objects.get(noc="FCWL")
        self.assertEqual(kernow.url, "https://www.firstbus.co.uk/cornwall")
        self.assertEqual(kernow.twitter, "by_Kernow")
        self.assertEqual(1, kernow.operatorcode_set.count())
        self.assertEqual(1, kernow.licences.count())

        cymru = Operator.objects.get(noc="FCYM")
        self.assertEqual(cymru.name, "First Cymru")

        notb = Operator.objects.get(noc="NOTB")
        self.assertEqual(notb.url, "")

        amsy = Operator.objects.get(noc="AMSY")
        self.assertEqual(amsy.name, "Arriva Merseyside")

        # status page
        response = self.client.get("/status")
        self.assertContains(
            response,
            """<th scope="row">National Operator Codes</th>
            <td>4 Jun 2024, 3:18 p.m.</td>""",
        )

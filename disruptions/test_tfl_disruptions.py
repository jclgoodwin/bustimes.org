from django.conf import settings
from django.core.management import call_command
from django.test import TestCase
from vcr import use_cassette

from busstops.models import DataSource, Region, Service


class TfLDisruptionsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        region = Region.objects.create(id="L", name="L")
        source = DataSource.objects.create(name="L")
        Service.objects.create(
            line_name="211",
            service_code="211",
            current=True,
            region=region,
            source=source,
        )
        DataSource.objects.create(name="TfL")

    def test_siri_sx_request(self):
        vcr_dir = settings.BASE_DIR / "fixtures" / "vcr"

        with use_cassette(
            str(vcr_dir / "tfl_disruptions.yaml"), decode_compressed_response=True
        ) as cassette:
            with self.assertNumQueries(102):
                call_command("tfl_disruptions")

            cassette.rewind()

            with self.assertNumQueries(100):
                call_command("tfl_disruptions")

        response = self.client.get("/situations")

        situation = response.context["situations"][0]

        self.assertEqual(
            situation.situation_number, "70c2d01c46664fb70c7b1ad11ff7fc8ace2a"
        )
        self.assertEqual(situation.reason, "")
        self.assertEqual(situation.summary, "VICTORIA BUS STATION")
        self.assertEqual(
            situation.text,
            "ROUTES 11 211 C1 N11 westbound are now departing from "
            "Victoria Station stop (R) on Buckingham Palace Road.",
        )

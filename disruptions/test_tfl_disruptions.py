from django.conf import settings
from django.core.management import call_command
from django.test import TestCase
from vcr import use_cassette

from busstops.models import DataSource, Region, Service

from .models import Situation


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

            with self.assertNumQueries(101):
                call_command("tfl_disruptions")

        situation = Situation.objects.first()

        self.assertEqual(
            situation.situation_number, "7df5fb8a20c132f4c90bf215e079e39e1b8f"
        )
        self.assertEqual(situation.reason, "")
        self.assertEqual(situation.summary, "")
        self.assertEqual(
            situation.text,
            "VICTORIA BUS STATION: "
            "ROUTES 11 211 C1 N11 westbound are now departing from "
            "Victoria Station stop (R) on Buckingham Palace Road.",
        )

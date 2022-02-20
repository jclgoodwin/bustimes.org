from pathlib import Path
from unittest.mock import patch
from vcr import use_cassette
from django.test import TestCase
from django.core.management import call_command
from busstops.models import Operator, DataSource


class MyTripTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.midland_classic = Operator.objects.create(id='MDCL', name="Midland Classic")
        Operator.objects.create(id='NIBS', name="Nibs")
        cls.source = DataSource.objects.create(
            name="MyTrip",
            url="https://mytrip-bustimes.api.passengercloud.com/ticketing/topups",
            settings={"x-api-key": ""}
        )

    def test_mytrip(self):
        path = Path(__file__).resolve().parent / 'data'

        with use_cassette(str(path / 'mytrip.yaml'), decode_compressed_response=True):

            with patch("builtins.print") as mocked_print:
                with patch("builtins.input", return_value="NIBS") as mocked_input:
                    call_command("mytrip_ticketing", "")

            mocked_print.assert_called_with(
                "✔️ ", self.midland_classic, "Midland Classic"
            )
            mocked_input.assert_called_with(
                "Operator matching query does not exist. York Pullman. Manually enter NOC: "
            )

            response = self.client.get("/operators/midland-classic/tickets")
            self.assertContains(response, "Burton &amp; South Derbys zone (excluding contracts and route 20)")

            response = self.client.get("/operators/midland-classic/tickets/34876152-181c-59fc-8276-4cd7a235db69")
            self.assertContains(response, """<p class="price">£2.50</p>""")

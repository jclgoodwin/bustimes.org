from pathlib import Path
from vcr import use_cassette
from django.test import TestCase
from django.core.management import call_command
from busstops.models import Operator, DataSource


class MyTripTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.midland_classic = Operator.objects.create(id='MDCL', name="Midland Classic")
        cls.source = DataSource.objects.create(
            name="MyTrip",
            url="https://mytrip-bustimes.api.passengercloud.com/ticketing/topups",
            settings={"x-api-key": ""}
        )

    def test_mytrip(self):
        path = Path(__file__).resolve().parent / 'data'

        with use_cassette(str(path / 'mytrip.yaml'), decode_compressed_response=True):

            call_command("mytrip_ticketing", "")

            response = self.client.get("/operators/midland-classic/tickets")
            self.assertContains(response, "Burton &amp; South Derbys zone (excluding contracts and route 20)")

            response = self.client.get("/operators/midland-classic/tickets/34876152-181c-59fc-8276-4cd7a235db69")
            self.assertContains(response, """<p class="price">£2.50</p>""")

from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from vcr import use_cassette

from busstops.models import DataSource, Operator, OperatorCode, Service


class MyTripTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.midland_classic = Operator.objects.create(
            noc="MDCL", name="Midland Classic"
        )
        # so MyTrip tab will show on operator page:
        service = Service.objects.create(current=True)

        source = DataSource.objects.create(name="National Operator Codes")
        operator = Operator.objects.create(noc="NIBS", name="Nibs")
        OperatorCode.objects.create(code="NIBS", operator=operator, source=source)
        service.operator.add(operator)

        cls.source = DataSource.objects.create(
            name="MyTrip",
            url="https://mytrip-bustimes.api.passengercloud.com/ticketing/topups",
            settings={"x-api-key": ""},
        )
        OperatorCode.objects.create(code="BEANS", operator=operator, source=cls.source)

    def test_mytrip(self):
        path = Path(__file__).resolve().parent / "data"

        with use_cassette(
            str(path / "mytrip.yaml"), decode_compressed_response=True
        ) as cassette:
            # fake inputting "NIBS" when asked for a matching operator code:
            with (
                patch("builtins.print") as mocked_print,
                patch("builtins.input", return_value="NIBS") as mocked_input,
            ):
                call_command("mytrip_ticketing", "")

            mocked_print.assert_any_call("✔️ ", self.midland_classic, "Midland Classic")
            mocked_input.assert_any_call(
                "Operator matching query does not exist. York Pullman. Manually enter NOC: "
            )
            mocked_print.assert_any_call("to_delete=<QuerySet [<OperatorCode: BEANS>]>")

            # run again:
            cassette.rewind()
            with patch("builtins.print") as mocked_print:
                call_command("mytrip_ticketing", "")
            mocked_print.assert_any_call("✔️ ", "Midland Classic")
            mocked_print.assert_any_call("✔️ ", "York Pullman")

            response = self.client.get("/operators/midland-classic/tickets")
            self.assertContains(
                response,
                "Burton &amp; South Derbys zone (excluding contracts and route 20)",
            )

            response = self.client.get(
                "/operators/midland-classic/tickets/34876152-181c-59fc-8276-4cd7a235db69"
            )
            self.assertContains(response, """<p class="price">£2.50</p>""")

        response = self.client.get("/operators/nibs")
        self.assertContains(response, ">Tickets<")
        self.assertContains(response, ">National operator code<")
        self.assertContains(response, ">NIBS<")

        response = self.client.get("/services/service")
        self.assertContains(response, ">the MyTrip app<")

from pathlib import Path
import time_machine
import datetime
import vcr
from django.test import TestCase
from django.core.management import call_command
from busstops.models import Region, Operator, DataSource, StopPoint
from ..commands import import_live_jersey


VCR_DIR = Path(__file__).resolve().parent / "vcr"


class JerseyImportTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Region.objects.create(id="JE")
        Operator.objects.create(noc="libertybus", region_id="JE")

    def test_stops(self):
        call_command("jersey_stops")
        self.assertEqual(StopPoint.objects.count(), 763)

    def test_routes(self):
        with vcr.use_cassette(str(VCR_DIR / "jersey_routes.yaml")):
            call_command("jersey_routes")

        response = self.client.get("/regions/JE")
        self.assertContains(
            response,
            """{
    background: #96DCFD;
    border-color: #000;
    color: #000;
}""",
        )

    @vcr.use_cassette(
        str(VCR_DIR / "import_live_jersey.yaml"),
        decode_compressed_response=True,
    )
    @time_machine.travel(datetime.datetime(2018, 8, 21, 0, 0, 9))
    def test_handle(self):
        command = import_live_jersey.Command()
        items = command.get_items()

        command.source = DataSource.objects.create(datetime="2018-08-06T22:41:15+01:00")

        vehicle, created = command.get_vehicle(items[0])
        self.assertEqual("330", str(vehicle))
        self.assertTrue(created)

        journey = command.get_journey(items[0], vehicle)
        self.assertIsNone(journey.service)

        # test a time before midnight (yesterday)
        location = command.create_vehicle_location(items[0])
        self.assertEqual(43, location.heading)

        self.assertEqual(
            "2018-08-20 23:59:00+00:00", str(command.get_datetime(items[0]))
        )

        # test a time after midnight (today)
        journey = command.get_journey(items[1], vehicle)

        location = command.create_vehicle_location(items[1])
        self.assertEqual(204, location.heading)

        self.assertEqual(
            "2018-08-21 00:00:04+00:00", str(command.get_datetime(items[1]))
        )

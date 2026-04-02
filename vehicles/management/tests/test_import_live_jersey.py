from pathlib import Path
import fakeredis
import time_machine
import vcr
from unittest.mock import patch
from django.test import TestCase
from django.core.management import call_command
from busstops.models import Region, Operator, StopPoint

from ...models import VehicleJourney


VCR_DIR = Path(__file__).resolve().parent / "vcr"


class JerseyImportTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Region.objects.create(id="JE")
        Operator.objects.create(noc="libertybus", region_id="JE")

    def test_stops(self):
        with self.assertNumQueries(5):
            call_command("jersey_stops")
        with self.assertNumQueries(2):
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
    @time_machine.travel("2025-10-15T10:20:00Z")
    def test_handle(self):
        redis_client = fakeredis.FakeStrictRedis(version=7)

        with (
            patch(
                "vehicles.management.import_live_vehicles.redis_client", redis_client
            ),
            patch(
                "vehicles.management.import_live_vehicles.sleep",
                side_effect=[None, None, Exception],
            ),
            self.assertRaises(Exception),
        ):
            call_command("import_live_jersey")

        with patch("vehicles.views.redis_client", redis_client):
            positions = self.client.get("/vehicles.json").json()
            self.assertEqual(positions[0]["datetime"], "2025-10-15T11:16:36+01:00")
            self.assertEqual(positions[1]["datetime"], "2025-10-15T11:16:51+01:00")
            self.assertEqual(positions[2]["datetime"], "2025-10-15T11:13:42+01:00")

            journey = VehicleJourney.objects.get(route_name="12")
            response = self.client.get(f"/journeys/{journey.id}.json")
            self.assertEqual(2, len(response.json()["locations"]))

            journey = VehicleJourney.objects.get(route_name="12A")
            response = self.client.get(f"/journeys/{journey.id}.json")
            self.assertEqual(2, len(response.json()["locations"]))

            journey = VehicleJourney.objects.get(route_name="15")
            response = self.client.get(f"/journeys/{journey.id}.json")
            self.assertEqual(1, len(response.json()["locations"]))

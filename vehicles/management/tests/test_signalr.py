from pathlib import Path
from unittest import mock

import fakeredis
import vcr
import time_machine
from django.test import TestCase
from django.core.management import call_command

from busstops.models import DataSource, Operator, Region
from ...models import VehicleJourney


class SignalRTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        source = DataSource.objects.create(
            name="signalr", url="https://example.com/hub"
        )
        DataSource.objects.create(name="IM")
        source.save()
        Region.objects.create(name="Isle of Man", id="IM")
        Operator.objects.create(noc="bus-vannin", name="Man I Feel Like a Bus")

    def test_get_journey(self):
        redis_client = fakeredis.FakeStrictRedis(version=7)

        with (
            vcr.use_cassette(
                str(Path(__file__).resolve().parent / "vcr" / "signalr.yaml")
            ),
            mock.patch(
                "vehicles.management.import_live_vehicles.redis_client", redis_client
            ),
            time_machine.travel("2025-06-20", tick=False),
            self.assertNumQueries(565),
            self.assertRaises(vcr.errors.CannotOverwriteExistingCassetteException),
        ):
            call_command("signalr", "signalr")

        self.assertEqual(VehicleJourney.objects.count(), 63)

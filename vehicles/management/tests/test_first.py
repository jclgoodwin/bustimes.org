from pathlib import Path
from unittest import mock

import fakeredis
import vcr
import time_machine
from django.test import TestCase
from django.core.management import call_command

from busstops.models import DataSource, Operator
from ...models import VehicleJourney


class FirstTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        DataSource.objects.create(name="First", url="https://example.com/version")
        # DataSource.objects.create(name="IM")
        # source.save()
        # Region.objects.create(name="Isle of Man", id="IM")
        Operator.objects.create(noc="BDGR", name="Badgerline")
        # s = Service.objects.create(current=True, geometry="POLYGON ((1.2 52.6, 1.2 52.7, 1.3 52.7, 1.3 52.6, 1.2 52.6))")
        # s.operator.add(o)

    def test_get_journey(self):
        redis_client = fakeredis.FakeStrictRedis(version=7)

        with (
            vcr.use_cassette(
                str(Path(__file__).resolve().parent / "vcr" / "first.yaml")
            ),
            mock.patch(
                "vehicles.management.import_live_vehicles.redis_client", redis_client
            ),
            time_machine.travel("2025-06-20", tick=False),
            self.assertNumQueries(3),
            self.assertRaises(vcr.errors.CannotOverwriteExistingCassetteException),
        ):
            call_command("import_first", "BDGR")

        self.assertEqual(VehicleJourney.objects.count(), 0)

from pathlib import Path
from unittest.mock import patch

import time_machine
from django.core.management import call_command
from django.test import TestCase, override_settings

from busstops.models import DataSource, Operator, Region, Service

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@override_settings(DATA_DIR=FIXTURES_DIR)
class FlixbusTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Region.objects.create(id="GB", name="Great Britain")

        Operator.objects.create(noc="FLIX", name="FlixBus")
        Operator.objects.create(noc="EMBR", name="Ember")

        DataSource.objects.bulk_create(
            [
                DataSource(
                    name="Ember",
                ),
                DataSource(
                    name="FlixBus",
                ),
            ]
        )

    @time_machine.travel("2023-01-01")
    def test_import_gtfs(self):
        with patch(
            "bustimes.management.commands.import_gtfs_flixbus.download_if_changed",
            return_value=(True, None),
        ):
            call_command("import_gtfs_flixbus")

        response = self.client.get("/operators/flixbus")
        self.assertContains(response, "London - Northampton - Nottingham")
        self.assertContains(response, "London - Cambridge")

        service = Service.objects.get(line_name="004")

        response = self.client.get(service.get_absolute_url())
        self.assertContains(
            response, "<td>10:30</td><td>15:00</td><td>19:15</td><td>23:40</td>"
        )

        # British Summer Time:
        response = self.client.get(f"{service.get_absolute_url()}?date=2024-04-01")
        self.assertContains(
            response, "<td>10:30</td><td>15:00</td><td>19:15</td><td>23:40</td>"
        )

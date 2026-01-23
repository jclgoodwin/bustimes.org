from django.test import TestCase, override_settings

import time_machine
import vcr

from .models import Service
from .tasks import update_popular_services


class PopularPagesTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Service.objects.create(
            slug="x40-sheringham-cromer-norwich",
            line_name="X40",
            current=True,
        )
        Service.objects.create(
            slug="840-leeds-whitby",
            line_name="840",
            current=True,
        )
        Service.objects.create(
            slug="19-north-shields-ashington",
            line_name="19",
            current=True,
        )

    @override_settings(
        UMAMI_WEBSITE_ID="test-website-id",
        UMAMI_TOKEN="test-token",
        CACHES={
            "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
        },
    )
    def test_update_popular_services(self):
        # freeze time to match the recorded cassette (endAt=1769141554391ms)
        with (
            time_machine.travel(1769141554.391, tick=False),
            vcr.use_cassette("fixtures/vcr/popular_services.yaml"),
            self.assertNumQueries(1),
        ):
            update_popular_services()

        with self.assertNumQueries(3):
            response = self.client.get("/")
        self.assertContains(response, "Popular pages")
        self.assertContains(response, "X40")
        self.assertContains(response, "840")
        self.assertContains(response, "19")

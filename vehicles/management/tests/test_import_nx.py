from unittest.mock import patch

import fakeredis
import time_machine
import vcr
from django.conf import settings
from django.test import TestCase

from busstops.models import DataSource, Operator, Region, Service
from bustimes.models import Calendar, Route, Trip

from ...models import VehicleJourney
from ..commands.import_nx import Command as NatExpCommand, parse_datetime


class NatExpTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        gb = Region.objects.create(id="GB")
        Operator.objects.create(noc="NATX", name="National Express", region=gb)

        cls.source = DataSource.objects.create(name="Nathaniel Express")

        service = Service.objects.create(line_name="491", current=True)
        service.operator.add("NATX")
        route = Route.objects.create(service=service, source=cls.source)
        calendar = Calendar.objects.create(
            sat=True,
            start_date="2022-06-01",
        )
        Trip.objects.create(
            route=route, calendar=calendar, start="15:00:00", end="16:00:00"
        )

    def test_parse_datetime(self):
        self.assertEqual(
            str(parse_datetime("2021-10-31 00:00:00")), "2021-10-31 00:00:00+01:00"
        )
        self.assertEqual(
            str(parse_datetime("2021-10-31 01:05:00")), "2021-10-31 01:05:00+01:00"
        )  # ambiguous time
        self.assertEqual(
            str(parse_datetime("2021-10-31 02:05:00")), "2021-10-31 02:05:00+00:00"
        )

        self.assertEqual(
            str(parse_datetime("2021-03-28 00:00:00")), "2021-03-28 00:00:00+00:00"
        )
        self.assertEqual(
            str(parse_datetime("2021-03-28 01:05:00")), "2021-03-28 01:05:00+00:00"
        )  # non existent time
        self.assertEqual(
            str(parse_datetime("2021-03-28 02:05:00")), "2021-03-28 02:05:00+01:00"
        )

    @patch("vehicles.management.commands.import_nx.sleep")
    @patch(
        "vehicles.management.commands.import_nx.redis_client",
        fakeredis.FakeStrictRedis(version=7),
    )
    def test_new(self, sleep):
        source = DataSource.objects.get()
        source.datetime = parse_datetime("2022-06-25 15:00:00")

        command = NatExpCommand()
        command.source = source
        command.source.url = "https://nx.origin-dev.utrack.com/api/public-origin-departures-by-route-v1/{}?"
        # command.operators = ["NATX"]

        with time_machine.travel(source.datetime):
            line_names = list(command.get_line_names())
            self.assertEqual(line_names, ["491"])

            with vcr.use_cassette(
                str(settings.BASE_DIR / "fixtures" / "vcr" / "natexp.yaml"),
                decode_compressed_response=True,
            ):
                command.update()

        self.assertTrue(sleep.called)

        self.assertEqual(1, VehicleJourney.objects.all().count())

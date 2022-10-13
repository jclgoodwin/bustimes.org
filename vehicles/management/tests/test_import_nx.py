from unittest.mock import patch

import time_machine
import vcr
from django.conf import settings
from django.test import TestCase

from busstops.models import DataSource, Operator, Region, Service
from bustimes.models import Calendar, Route, Trip

from ...models import Vehicle, VehicleJourney
from ..commands.import_aircoach import Command as AircoachCommand
from ..commands.import_natexp import Command as NewNatExpCommand
from ..commands.import_nx import Command as NatExpCommand
from ..commands.import_nx import parse_datetime


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
            mon=False,
            tue=False,
            wed=False,
            thu=False,
            fri=False,
            sat=True,
            sun=False,
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
    def test_update(self, sleep):
        source = DataSource.objects.get()
        source.datetime = parse_datetime("2020-01-31 00:00:00")

        aircoach_command = AircoachCommand()
        aircoach_command.source = source

        nat_exp_command = NatExpCommand()
        nat_exp_command.source = source

        # first, test with missing timetable data:

        with time_machine.travel(source.datetime):
            with self.assertNumQueries(1):
                items = list(aircoach_command.get_items())
                self.assertEqual(len(items), 0)

            with self.assertNumQueries(2):
                items = list(nat_exp_command.get_items())
                self.assertEqual(len(items), 0)

            self.assertFalse(sleep.called)

        # and now:

        with time_machine.travel("2022-06-25T14:00:00.000Z"):
            with vcr.use_cassette(
                str(settings.BASE_DIR / "fixtures" / "vcr" / "nx.yaml"),
                decode_compressed_response=True,
            ):
                nat_exp_command.update()

        self.assertEqual(4, VehicleJourney.objects.all().count())

        response = self.client.get("/vehicles.json").json()
        self.assertEqual(response[0]["destination"], "Great Yarmouth")
        self.assertEqual(response[0]["delay"], 4140.0)

        self.assertEqual(5, Vehicle.objects.all().count())

        response = self.client.get("/operators/national-express/vehicles")
        self.assertContains(response, "BX65 WAJ")

    @patch("vehicles.management.commands.import_nx.sleep")
    def test_new(self, sleep):
        source = DataSource.objects.get()
        source.datetime = parse_datetime("2022-06-25 15:00:00")

        command = NewNatExpCommand()
        command.source = source

        line_names = list(command.get_line_names())
        self.assertEqual(line_names, [])

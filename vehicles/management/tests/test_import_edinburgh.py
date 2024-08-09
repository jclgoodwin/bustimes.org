from pathlib import Path
from unittest import mock

import fakeredis
import vcr
from django.test import TestCase

from busstops.models import DataSource, Operator, Region, Service

from ..commands.import_edinburgh import Command


class EdinburghImportTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        source = DataSource.objects.create(
            name="TfE", url="https://tfe-opendata.com/api/v1/vehicle_locations"
        )
        source.save()
        source.refresh_from_db()
        Region.objects.create(name="Scotland", id="S")
        cls.operator_1 = Operator.objects.create(
            name="Lothian Buses", noc="LOTH", region_id="S"
        )
        cls.operator_2 = Operator.objects.create(
            name="Edinburgh Trams", noc="EDTR", region_id="S"
        )
        cls.service = Service.objects.create(line_name="11", current=True)
        cls.service.operator.add(cls.operator_2)
        cls.source = source

    def test_get_journey(self):
        redis_client = fakeredis.FakeStrictRedis(version=7)

        with vcr.use_cassette(
            str(
                Path(__file__).resolve().parent
                / "vcr"
                / "edinburgh_vehicle_locations.yaml"
            )
        ) as cassette:
            command = Command()
            command.do_source()

            with mock.patch(
                "vehicles.management.import_live_vehicles.redis_client", redis_client
            ):
                with self.assertNumQueries(28):
                    command.update()

                self.assertEqual({}, command.vehicle_cache)

                cassette.rewind()
                del command.previous_locations["454"]

                with self.assertNumQueries(1):
                    command.update()

            self.assertEqual(1, len(command.vehicle_cache))

        journey = command.source.vehiclejourney_set.first()

        self.assertEqual("6212", journey.code)
        self.assertEqual("Hyvots Bank", journey.destination)
        self.assertEqual(self.service, journey.service)

        self.assertTrue(journey.service.tracking)
        response = self.client.get(journey.service.get_absolute_url())
        self.assertContains(response, '/vehicles">Vehicles</a>')

        response = self.client.get(self.operator_2.get_absolute_url())
        self.assertContains(response, '/map">Map</a>')
        self.assertContains(response, '/vehicles">Vehicles</a>')

    def test_vehicle_location(self):
        command = Command()
        command.source = self.source

        item = {
            "last_gps_fix_secs": 19,
            "source": "Icomera Wi-Fi",
            "vehicle_id": "3030",
            "heading": 76,
            "latitude": 55.95376,
            "longitude": -3.18718,
            "last_gps_fix": 1554034642,
            "ineo_gps_fix": 1554038242,
        }
        location = command.create_vehicle_location(item)
        self.assertEqual(76, location.heading)
        self.assertTrue(location.latlong)

        self.assertEqual("2019-03-31 12:17:22+00:00", str(command.get_datetime(item)))

from pathlib import Path
from unittest import mock

import fakeredis
import vcr
from django.test import TestCase

from busstops.models import DataSource, Operator, Region, Service
from ...models import Vehicle
from ..commands.lothian import Command


class EdinburghImportTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        source = DataSource.objects.create(name="TfE")
        source.save()
        source.refresh_from_db()
        Region.objects.create(name="Scotland", id="S")
        cls.operator_1 = Operator.objects.create(
            name="Lothian Buses", noc="LOTH", region_id="S"
        )
        cls.operator_2 = Operator.objects.create(
            name="Edinburgh Trams", noc="EDTR", region_id="S"
        )
        cls.service = Service.objects.create(line_name="N14", current=True)
        cls.service.operator.add(cls.operator_1)
        cls.source = source
        Vehicle.objects.create(operator_id="EDTR", source=source, code="1120")

    def test_lothian_avl(self):
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
                with self.assertNumQueries(150):
                    command.update()

                cassette.rewind()

                # make it think 1 vehicle has moved
                del command.identifiers["1116"]

                with self.assertNumQueries(4):
                    command.update()

        journey = command.source.vehiclejourney_set.first()

        self.assertEqual("NovWedAL23907804", journey.code)
        self.assertEqual("Surgeons' Hall", journey.destination)
        self.assertEqual(self.service, journey.service)

        self.assertTrue(journey.service.tracking)
        response = self.client.get(journey.service.get_absolute_url())
        self.assertContains(response, '/vehicles">Vehicles</a>')

        response = self.client.get(self.operator_1.get_absolute_url())
        self.assertContains(response, '/map">Map</a>')
        self.assertContains(response, '/vehicles">Vehicles</a>')

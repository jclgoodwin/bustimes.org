from unittest.mock import patch

import fakeredis
from django.test import TestCase

from busstops.models import DataSource, Operator, Region, OperatorCode

from ...models import Vehicle
from ..commands.import_polar import Command


@patch(
    "vehicles.management.import_live_vehicles.redis_client",
    fakeredis.FakeStrictRedis(),
)
class PolarTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        source = DataSource.objects.create(name="Loach's")
        region = Region.objects.create(id="WM")
        operator = Operator.objects.create(
            noc="LCHS", name="Loach's Coaches", region=region
        )
        OperatorCode.objects.create(operator=operator, source=source, code="LOAC")

    def test_do_source(self):
        command = Command()
        command.source_name = ""
        command.wait = 0
        with self.assertRaises(DataSource.DoesNotExist):
            command.handle("Loach's Coaches")

    def test_handle_items(self):
        command = Command()
        command.source_name = command.vehicle_code_scheme = "Loach's"
        command.do_source()

        with patch(
            "vehicles.management.commands.import_polar.Command.get_items",
            return_value=[
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [-1.535843, 53.797578],
                    },
                    "properties": {
                        "direction": "outbound",
                        "line": "POO",
                        "vehicle": "3635",
                    },
                }
            ],
        ):
            command.update()

        vehicle = Vehicle.objects.get()
        self.assertEqual(str(vehicle), "3635")
        self.assertEqual(vehicle.fleet_code, "3635")
        self.assertEqual(vehicle.fleet_number, 3635)
        self.assertEqual(str(vehicle.operator), "Loach's Coaches")

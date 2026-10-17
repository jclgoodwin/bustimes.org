from unittest.mock import Mock, patch

from django.core.management import call_command
from django.test import TestCase
from google.transit import gtfs_realtime_pb2

from busstops.models import Operator

from ...models import Vehicle
from ..commands.import_gtfsr_feed import parse_feed


class GTFSRFeedTest(TestCase):
    def test_parse_feed(self):
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.header.gtfs_realtime_version = "2.0"
        feed.header.timestamp = 1792150470
        for vehicle_id in ("1", "2"):
            entity = feed.entity.add(id=vehicle_id)
            entity.vehicle.vehicle.id = vehicle_id
        data = feed.SerializeToString()

        self.assertEqual(parse_feed(data), feed)

        # declare the first entity's length to be 1 byte too short,
        # like the Skopje feed sometimes does
        entity_length = len(feed.entity[0].SerializeToString())
        header_length = len(feed.header.SerializeToString()) + 2
        corrupt = bytearray(data)
        assert corrupt[header_length + 1] == entity_length
        corrupt[header_length + 1] -= 1

        corrupt_feed = parse_feed(bytes(corrupt))
        self.assertEqual(corrupt_feed.header.timestamp, 1792150470)
        self.assertEqual(
            [entity.vehicle.vehicle.id for entity in corrupt_feed.entity], ["1", "2"]
        )

    def test_import_zditm_vehicles(self):
        Operator.objects.create(noc="ZDITM", name="ZDiTM Szczecin")
        Vehicle.objects.create(code="254", fleet_code="122+123", operator_id="ZDITM")
        response = Mock(
            json=lambda: {
                "data": [
                    {
                        "vehicle_type": "tram",
                        "vehicle_id": 254,
                        "vehicle_number": "122+123",
                        "vehicle_model": "Moderus Beta <->",
                        "vehicle_operator": "Tramwaje Szczecińskie",
                    },
                    {
                        "vehicle_type": "bus",
                        "vehicle_id": 3,
                        "vehicle_number": "1050",
                        "vehicle_model": "Solaris Urbino 18",
                        "vehicle_operator": "SPA Klonowica",
                    },
                ]
            }
        )
        with patch(
            "vehicles.management.commands.import_zditm_vehicles.requests.get",
            return_value=response,
        ):
            call_command("import_zditm_vehicles")

        vehicle = Vehicle.objects.select_related("vehicle_type").get()
        self.assertEqual(vehicle.vehicle_type.name, "Moderus Beta (bidirectional)")
        self.assertEqual(vehicle.vehicle_type.style, "tram")
        self.assertEqual(vehicle.data, {"Operator": "Tramwaje Szczecińskie"})

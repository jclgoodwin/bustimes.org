from unittest.mock import patch

import fakeredis
from django.test import TestCase

from busstops.models import DataSource, Operator, Region, Service, ServiceCode

from ...models import Vehicle, VehicleJourney
from ..commands import import_bushub


class BusHubTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        DataSource.objects.create()
        Region.objects.create(id="WM")
        Operator.objects.create(
            noc="DIAM", name="Graphite Buses", region_id="WM", parent="Rotala"
        )
        Operator.objects.create(
            noc="WNGS", name="Paul McCartney & Wings", region_id="WM", parent="Rotala"
        )
        service_a = Service.objects.create(
            service_code="44a", line_name="44", tracking=True
        )
        service_b = Service.objects.create(
            service_code="44b", line_name="44", tracking=True
        )
        service_a.operator.add("DIAM")
        service_b.operator.add("DIAM")
        cls.service_c = Service.objects.create(
            service_code="44", line_name="44", tracking=True
        )
        cls.service_c.operator.add("WNGS")
        cls.vehicle = Vehicle.objects.create(code="20052", operator_id="WNGS")
        ServiceCode.objects.create(code="44a", scheme="SIRI", service=cls.service_c)

    @patch(
        "vehicles.management.import_live_vehicles.redis_client",
        fakeredis.FakeStrictRedis(version=7),
    )
    def test_handle(self):
        command = import_bushub.Command()
        command.source_name = ""
        command.do_source()

        item = {
            "RouteDescription": None,
            "DestinationStopName": "Bus Station",
            "DestinationStopLocality": "Redditch",
            "DestinationStopFullName": "Bus Station, Redditch",
            "LastUpdated": "2018-08-31T22:49:11",
            "DepartureTime": "2018-08-31T22:45:00",
            "Latitude": "52.30236",
            "Longitude": "-1.926653",
            "RecordedAtTime": "2018-08-31T22:49:33",
            "ValidUntilTime": "2018-08-31T22:49:33",
            "LineRef": "R57",
            "DirectionRef": "outbound",
            "PublishedLineName": "44a",
            "OperatorRef": "DIAM",
            "Bearing": "143",
            "BlockRef": "2027",
            "TicketMachineServiceCode": "R57",
            "JourneyCode": "2245",
            "DbCreated": "2018-08-31T22:49:35.993",
            "DataSetId": 2091413,
            "DestinationRef": "2000G700311",
            "NextStopName": None,
            "NextStopLocality": None,
            "NextStopFullName": "",
            "StopPointRef": None,
            "CurrentStopName": "",
            "CurrentStopLocality": "",
            "CurrentStopFullName": "",
            "VehicleAtStop": False,
            "VisitNumber": "",
            "VehicleRef": "11111",
            "Destination": None,
        }

        with self.assertNumQueries(9), patch("builtins.print") as mocked_print:
            command.handle_item(item)
            command.save()

        mocked_print.assert_called()

        item["OperatorRef"] = "DIAM"

        with self.assertNumQueries(1):
            command.handle_item(item)
            command.save()

        journey = VehicleJourney.objects.get()
        self.assertEqual("2018-08-31 21:45:00+00:00", str(journey.datetime))
        # self.assertEqual(143, location.heading)
        self.assertEqual("DIAM", journey.vehicle.operator_id)
        self.assertIsNone(journey.service)

        item["OperatorRef"] = "WNGS"
        item["VehicleRef"] = "20052"
        item["Bearing"] = "-1"
        with self.assertNumQueries(7):
            command.handle_item(item)
            command.save()
        self.assertEqual(2, Vehicle.objects.count())
        self.vehicle.refresh_from_db()
        # self.assertIsNotNone(self.vehicle.latest_location)
        # self.assertIsNone(self.vehicle.latest_location.heading)
        self.assertEqual(self.service_c, self.vehicle.latest_journey.service)

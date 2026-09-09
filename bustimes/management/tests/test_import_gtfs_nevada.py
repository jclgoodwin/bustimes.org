import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import fakeredis
import time_machine
from django.core.management import call_command
from django.test import TestCase, override_settings
from google.protobuf import json_format
from google.transit import gtfs_realtime_pb2

from busstops.models import Service
from vehicles.management.commands import import_gtfsr_nevada
from vehicles.models import Vehicle, VehicleJourney

from ...models import Trip

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


# test data in `rtcsnv.zip` dir (not a real zipfile) in fixtures dir
@override_settings(DATA_DIR=FIXTURES_DIR)
class NevadaTest(TestCase):
    def test_not_modified(self):
        with (
            patch(
                "bustimes.management.commands.import_gtfs_nevada.download_if_modified",
                return_value=(False, None),
            ),
            self.assertNumQueries(4),
        ):
            call_command("import_gtfs_nevada")

    @time_machine.travel("2026-08-04", tick=False)
    def test_import_gtfs_nevada(self):
        # a vehicle with an implausibly future timestamp
        self.enterContext(
            self.assertLogs("vehicles.management.import_live_vehicles", "WARNING")
        )

        with patch(
            "bustimes.management.commands.import_gtfs_nevada.download_if_modified",
            return_value=(
                True,
                datetime.datetime(2024, 6, 18, 10, 0, 0, tzinfo=datetime.UTC),
            ),
        ):
            call_command("import_gtfs_nevada")

            self.assertEqual(Service.objects.all().count(), 2)

            # re-importing shouldn't re-create services

            call_command("import_gtfs_nevada")
            self.assertEqual(Service.objects.all().count(), 2)

        response = self.client.get("/operators/rtcsnv")
        self.assertContains(response, """<a href="/services/deuce-the-deucestrip">""")

        response = self.client.get("/services/deuce-the-deucestrip?detailed=0")
        self.assertContains(response, "/stops/rtcsnv-6038")

        response = self.client.get("/stops/rtcsnv-6038")
        # Pacific Time
        self.assertContains(
            response, """<input type="time" name="time" value="16:00">"""
        )

        # test GTFS-RT
        feed = gtfs_realtime_pb2.FeedMessage()
        json_format.ParseDict(
            {
                "header": {"gtfsRealtimeVersion": "2.0", "timestamp": "1785751500"},
                "entity": [
                    {
                        "id": "20450",
                        "vehicle": {
                            "trip": {
                                "tripId": "358024702",
                                "routeId": "4740",
                                "startDate": "20260803",
                                "startTime": "03:00:00",
                                "scheduleRelationship": "SCHEDULED",
                            },
                            "vehicle": {"id": "20450", "label": "20450"},
                            "position": {
                                "latitude": 36.10913,
                                "longitude": -115.17262,
                            },
                            "timestamp": "1785751500",  # 03:05 Pacific Time
                        },
                    },
                    {
                        "id": "26627",
                        "vehicle": {
                            "trip": {
                                "tripId": "358022630",
                                "routeId": "4725",
                                "startDate": "20260803",
                                "startTime": "26:25:00",
                                "directionId": 0,
                                "scheduleRelationship": "SCHEDULED",
                            },
                            "stopId": "2770",
                            "vehicle": {"id": "26627", "label": "26627"},
                            "position": {
                                "latitude": 36.18293,
                                "longitude": -115.31084,
                            },
                            "timestamp": "1785835126",
                            "currentStatus": "STOPPED_AT",
                            "occupancyStatus": "MANY_SEATS_AVAILABLE",
                            "currentStopSequence": 1,
                            "occupancyPercentage": 2,
                        },
                    },
                ],
            },
            feed,
        )
        response = Mock(status_code=200, content=feed.SerializeToString(), headers={})

        command = import_gtfsr_nevada.Command()
        command.do_source()

        with (
            patch.object(command.session, "get", return_value=response),
            patch(
                "vehicles.management.import_live_vehicles.redis_client",
                fakeredis.FakeStrictRedis(),
            ),
        ):
            command.update()

        trip = Trip.objects.get(vehicle_journey_code="358024702")
        journey = VehicleJourney.objects.get(code="358024702")
        self.assertEqual(journey.trip, trip)
        self.assertEqual(journey.service, trip.route.service)
        self.assertEqual(journey.route_name, "DEUCE")
        self.assertEqual(journey.destination, "Deuce on The Strip Northbound")
        self.assertEqual(str(journey.datetime), "2026-08-03 10:00:00+00:00")
        self.assertEqual(str(journey.date), "2026-08-03")

        vehicle = Vehicle.objects.get(code="26627")
        self.assertEqual(vehicle.fleet_code, "26627")

        journey = VehicleJourney.objects.get(code="358022630")
        # start_time "26:25:00" and date 2026-08-03
        # means 02:25 Pacific Time the next day
        self.assertEqual(str(journey.date), "2026-08-03")
        self.assertEqual(str(journey.datetime), "2026-08-04 09:25:00+00:00")

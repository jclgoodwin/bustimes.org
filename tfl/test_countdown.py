from unittest.mock import patch

import fakeredis
import requests
import time_machine
from django.test import TestCase

from api.views import VehicleJourneyViewSet
from busstops.models import StopPoint
from departures.sources import TflDepartures

from . import countdown

FEED = """[4,"1.0",1791889626337]
[3,"20261009"]
[1,"St Mary Axe","490012783W","25","Holborn Viaduct",78215,"SK20AYT",1791889744000]
[1,"St Mary Axe","490012783W","25","Holborn Viaduct",78232,"SK20AYH",1791890133000]
[1,"Aldgate","490000004B","25","Holborn Viaduct",78215,"SK20AYT",1791889600000]
[1,"Bank","490000013S","25","Ilford",51063,"SK20AYT",1791893000000]
[1,"Bank","490000013S","25","Ilford",51064,null,1791893100000]
[1,"Loughton",null,"20","Walthamstow",61001,"LX11BBB",1791893200000]
"""


@time_machine.travel("2026-10-13T11:05:00Z", tick=False)
class CountdownTest(TestCase):
    def setUp(self):
        self.redis_client = fakeredis.FakeStrictRedis()
        patcher = patch("tfl.countdown.redis_client", self.redis_client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def refresh(self):
        response = requests.Response()
        response.status_code = 200
        response._content = FEED.encode()
        with patch("tfl.countdown.requests.get", return_value=response):
            countdown.refresh()

    def test_parse(self):
        vehicles, stops = countdown.parse(FEED)
        self.assertEqual(len(vehicles), 3)
        self.assertNotIn(None, vehicles)
        self.assertNotIn(None, stops)
        self.assertEqual(len(stops["490000013S"]), 2)
        self.assertEqual(len(stops["490012783W"]), 2)
        self.assertEqual(
            vehicles["SK20AYT"][0],
            {
                "naptanId": "490012783W",
                "stationName": "St Mary Axe",
                "tripId": "78215",
                "baseVersion": "20261009",
                "expectedArrival": "2026-10-13T11:09:04+00:00",
            },
        )
        self.assertEqual(
            stops["490012783W"][0],
            {
                "lineName": "25",
                "destinationName": "Holborn Viaduct",
                "vehicleId": "SK20AYT",
                "expectedArrival": "2026-10-13T11:09:04+00:00",
                "modeName": "bus",
            },
        )

    def test_stale_while_revalidate(self):
        # no data yet - refresh in the background, use the TfL API meanwhile
        with patch("tfl.tasks.refresh_countdown") as task:
            self.assertIsNone(countdown.get_vehicle_predictions("SK20AYT"))
            # only one refresh at a time
            self.assertIsNone(countdown.get_vehicle_predictions("SK20AYT"))
        task.assert_called_once_with()

        self.refresh()
        self.assertFalse(self.redis_client.exists(countdown.LOCK_KEY))

        with patch("tfl.tasks.refresh_countdown") as task:
            predictions = countdown.get_vehicle_predictions("SK20AYT")
            self.assertEqual(
                [item["stationName"] for item in predictions],
                ["St Mary Axe", "Aldgate", "Bank"],
            )
            # not in the feed - no predictions
            self.assertEqual(countdown.get_vehicle_predictions("LX11AAA"), [])
            self.assertEqual(len(countdown.get_stop_predictions("490012783W")), 2)
            task.assert_not_called()

            # stale - still use it while refreshing
            self.redis_client.delete(countdown.FRESH_KEY)
            self.assertEqual(len(countdown.get_stop_predictions("490012783W")), 2)
            task.assert_called_once()

        with (
            time_machine.travel("2026-10-13T11:07:00Z", tick=False),
            patch("tfl.tasks.refresh_countdown"),
        ):
            # (filter out predictions in the past)
            predictions = countdown.get_vehicle_predictions("SK20AYT")
            self.assertEqual(
                [item["stationName"] for item in predictions], ["St Mary Axe", "Bank"]
            )

    def test_error(self):
        with (
            patch("tfl.countdown.requests.get", side_effect=requests.Timeout),
            self.assertLogs("tfl.countdown", "WARNING"),
        ):
            countdown.refresh()
        self.assertFalse(self.redis_client.exists(countdown.VEHICLES_KEY))

    def test_consumers(self):
        self.refresh()

        data = VehicleJourneyViewSet.get_tfl_arrivals("SK20AYT")
        self.assertEqual(len(data), 3)

        stop = StopPoint(atco_code="490012783W", stop_type="BCS")
        rows = TflDepartures(stop, []).get_departures()
        self.assertEqual([row["vehicle"] for row in rows], ["SK20AYT", "SK20AYH"])
        self.assertEqual(rows[0]["service"], "25")
        self.assertEqual(rows[0]["destination"], "Holborn Viaduct")

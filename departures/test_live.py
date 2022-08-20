# coding=utf-8
"""Tests for live departures
"""
import vcr
import time_machine
from datetime import datetime, date
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.shortcuts import render

from busstops.models import (
    StopPoint,
    Service,
    Region,
    Operator,
    StopUsage,
    AdminArea,
    DataSource,
    SIRISource,
)
from bustimes.models import Route, Trip, Calendar, StopTime
from vehicles.models import Vehicle, VehicleJourney
from vehicles.tasks import log_vehicle_journey
from . import live


class LiveDeparturesTest(TestCase):
    """Tests for live departures"""

    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(id="W", name="Wales")

        cls.london_stop = StopPoint.objects.create(
            pk="490014721F",
            common_name="Wilmot Street",
            locality_centre=False,
            active=True,
        )
        cls.cardiff_stop = StopPoint.objects.create(
            pk="5710WDB48471", common_name="Wood Street", active=True
        )

        cls.yorkshire_stop = StopPoint.objects.create(
            pk="3290YYA00215",
            naptan_code="32900215",
            common_name="Victoria Bar",
            active=True,
        )

        admin_area = AdminArea.objects.create(
            pk=109, atco_code=200, name="Worcestershire", region=cls.region
        )
        siri_source = SIRISource.objects.create(
            name="SPT",
            url="http://worcestershire-rt-http.trapezenovus.co.uk:8080",
            requestor_ref="Traveline_To_Trapeze",
        )
        cls.source = DataSource.objects.create()
        siri_source.admin_areas.add(admin_area)
        cls.worcester_stop = StopPoint.objects.create(
            pk="2000G000106",
            common_name="Crowngate Bus Station",
            locality_centre=False,
            active=True,
            admin_area=admin_area,
        )
        worcester_44 = Service.objects.create(
            service_code="44", line_name="44", region_id="W", date="2017-01-01"
        )
        worcester_44.operator.add(
            Operator.objects.create(noc="FMR", name="First Midland Red", region_id="W")
        )
        StopUsage.objects.create(stop=cls.worcester_stop, service=worcester_44, order=0)

        calendar = Calendar.objects.create(
            mon=True,
            tue=True,
            wed=True,
            thu=True,
            fri=True,
            sat=True,
            sun=True,
            start_date="2019-02-09",
            end_date="2019-02-09",
        )
        worcester_route = Route.objects.create(
            service=worcester_44, start_date="2017-03-04", source=cls.source, code="44"
        )
        cls.trip = Trip.objects.create(
            calendar=calendar,
            route=worcester_route,
            destination=cls.worcester_stop,
            start="0",
            end="11:00:00",
        )
        cls.worcs_stop_time = StopTime.objects.create(
            trip=cls.trip,
            sequence=0,
            arrival="10:54:00",
            departure="10:54:00",
            stop=cls.worcester_stop,
        )
        StopUsage.objects.create(
            stop_id=cls.worcester_stop.pk, service=worcester_44, order=1
        )

    def test_abstract(self):
        departures = live.Departures(None, ())
        self.assertIsNone(departures.get_request_url())
        self.assertRaises(
            NotImplementedError, departures.departures_from_response, None
        )

    def test_tfl(self):
        """Test the Transport for London live departures source"""

        service = Service.objects.create(
            service_code="tfl_60-8-_-y05",
            line_name="8",
            region_id="W",
            date="2017-01-01",
        )
        StopUsage.objects.create(stop=self.london_stop, service=service, order=1)
        route = Route.objects.create(source=self.source, service=service)
        trip = Trip.objects.create(route=route, start="0", end="1")
        StopTime.objects.create(trip=trip, stop=self.london_stop)

        with vcr.use_cassette("fixtures/vcr/tfl_arrivals.yaml"):
            row = live.TflDepartures(self.london_stop, [service]).get_departures()[0]
        self.assertEqual("Bow Church", row["destination"])
        self.assertEqual(service, row["service"])
        self.assertEqual(2016, row["live"].date().year)
        self.assertEqual(7, row["live"].date().month)
        self.assertEqual(26, row["live"].date().day)

        with vcr.use_cassette("fixtures/vcr/tfl_arrivals.yaml"):
            response = self.client.get("/stops/" + self.london_stop.pk)

        self.assertContains(
            response,
            """
                <h2>Next departures</h2>
                <table><tbody>
                    <tr><td><a href="/services/8">8</a></td><td>Bow Church</td>
                        <td><a href="/vehicles/tfl/LTZ1414#stop-490014721F">18:22⚡&#xfe0f;</a></td></tr>
                    <tr><td>D3</td><td>Bethnal Green, Chest Hospital</td>
                        <td><a href="/vehicles/tfl/LX59AOM#stop-490014721F">18:23⚡&#xfe0f;</a></td></tr>
                    <tr><td><a href="/services/8">8</a></td><td>Bow Church</td>
                        <td><a href="/vehicles/tfl/LTZ1243#stop-490014721F">18:26⚡&#xfe0f;</a></td></tr>
                    <tr><td>388</td><td>Stratford City</td>
                        <td><a href="/vehicles/tfl/YR59NPF#stop-490014721F">18:26⚡&#xfe0f;</a></td></tr>
                    <tr><td><a href="/services/8">8</a></td><td>Bow Church</td>
                        <td><a href="/vehicles/tfl/LTZ1407#stop-490014721F">18:33⚡&#xfe0f;</a></td></tr>
                    <tr><td>D3</td><td>Bethnal Green, Chest Hospital</td>
                        <td><a href="/vehicles/tfl/LX59AOL#stop-490014721F">18:33⚡&#xfe0f;</a></td></tr>
                    <tr><td><a href="/services/8">8</a></td><td>Bow Church</td>
                        <td><a href="/vehicles/tfl/LTZ1412#stop-490014721F">18:37⚡&#xfe0f;</a></td></tr>
                    <tr><td>388</td><td>Stratford City</td>
                        <td><a href="/vehicles/tfl/PF52TFX#stop-490014721F">18:44⚡&#xfe0f;</a></td></tr>
                    <tr><td>D3</td><td>Bethnal Green, Chest Hospital</td>
                        <td><a href="/vehicles/tfl/LX59AOA#stop-490014721F">18:44⚡&#xfe0f;</a></td></tr>
                    <tr><td><a href="/services/8">8</a></td><td>Bow Church</td>
                        <td><a href="/vehicles/tfl/LTZ1269#stop-490014721F">18:44⚡&#xfe0f;</a></td></tr>
                    <tr><td><a href="/services/8">8</a></td><td>Bow Church</td>
                        <td><a href="/vehicles/tfl/LTZ1393#stop-490014721F">18:49⚡&#xfe0f;</a></td></tr>
                </tbody></table>
            <p class="credit">⚡&#xfe0f; denotes ‘live’ times guessed (sometimes badly) from buses’ actual locations</p>
        """,
            html=True,
        )

    @time_machine.travel(date(2018, 10, 27))
    def test_translink_metro(self):
        operator = Operator.objects.create(
            noc="MET", name="Translink Metro", region_id="W"
        )
        stop = StopPoint.objects.create(
            atco_code="700000001415", active=True, locality_centre=False
        )
        service = Service.objects.create(
            service_code="2D_MET", line_name="2D", region_id="W", date="2017-01-01"
        )
        service.operator.add(operator)
        StopUsage.objects.create(stop=stop, service=service, order=0)
        route = Route.objects.create(source=self.source, service=service)
        trip = Trip.objects.create(route=route, start="0", end="1")
        StopTime.objects.create(trip=trip, stop=stop)

        with vcr.use_cassette("fixtures/vcr/translink_metro.yaml"):
            res = self.client.get(stop.get_absolute_url())
        self.assertNotContains(res, "<h3>")
        self.assertContains(
            res, "<tr><td>14B</td><td>City Express</td><td>08:22</td></tr>", html=True
        )
        self.assertContains(
            res,
            "<tr><td>1A</td><td>City Centre</td><td>07:54⚡&#xfe0f;</td></tr>",
            html=True,
        )

    def test_translink_metro_no_services_running(self):
        with vcr.use_cassette("fixtures/vcr/translink_metro.yaml", match_on=["body"]):
            departures = live.AcisHorizonDepartures(StopPoint(pk="700000000748"), ())
            self.assertEqual([], departures.get_departures())

    def test_edinburgh(self):
        vehicle_source = DataSource.objects.create(name="TfE")
        stop = StopPoint.objects.create(
            atco_code="6200245070",
            naptan_code="36238258",
            common_name="Crewe Bank",
            active=True,
        )
        operator = Operator.objects.create(noc="LOTH", name="Lothian Buses")
        service = Service.objects.create(line_name="14")
        service.operator.add(operator)
        StopUsage.objects.create(stop=stop, service=service, order=1)
        route = Route.objects.create(
            line_name="14", service=service, source=self.source, start_date="2022-06-13"
        )
        calendar = Calendar.objects.create(
            mon=True,
            tue=True,
            wed=True,
            thu=True,
            fri=True,
            sat=True,
            sun=True,
            start_date="2022-06-13",
        )
        trip = Trip.objects.create(
            calendar=calendar, route=route, destination=stop, start="0", end="24:00:00"
        )
        StopTime.objects.create(
            trip=trip, sequence=0, arrival="13:18:00", departure="13:18:00", stop=stop
        )
        vehicle = Vehicle.objects.create(source=vehicle_source, code="686")

        with time_machine.travel(datetime(2022, 6, 14, 13, 17)):
            with vcr.use_cassette(
                "fixtures/vcr/edinburgh.yaml", decode_compressed_response=True
            ):
                with self.assertNumQueries(12):
                    response = self.client.get(stop.get_absolute_url())
        self.assertContains(response, f'<a href="/vehicles/{vehicle.id}#map">')

    def test_west_midlands(self):
        stop = StopPoint.objects.create(
            atco_code="3800C419101",
            common_name="Farewell Lane",
            active=True,
        )
        operator = Operator.objects.create(noc="TCVW", name="National Express Coventry")
        service = Service.objects.create(line_name="8")
        service.operator.add(operator)
        StopUsage.objects.create(stop=stop, service=service, order=1)
        route = Route.objects.create(
            line_name="8", service=service, source=self.source, start_date="2022-06-13"
        )
        calendar = Calendar.objects.create(
            mon=True,
            tue=True,
            wed=True,
            thu=True,
            fri=True,
            sat=True,
            sun=True,
            start_date="2022-06-13",
        )
        trip = Trip.objects.create(
            calendar=calendar, route=route, destination=stop, start="0", end="24:00:00"
        )
        StopTime.objects.create(
            trip=trip, sequence=0, arrival="13:19:00", departure="13:19:00", stop=stop
        )

        with override_settings(
            TFWM={
                "app_id": "app_id",
                "app_key": "app_key",
            }
        ):
            with time_machine.travel(datetime(2022, 6, 26, 13, 10)):
                with vcr.use_cassette(
                    "fixtures/vcr/tfwm.yaml", decode_compressed_response=True
                ):
                    with self.assertNumQueries(11):
                        response = self.client.get(stop.get_absolute_url())
        self.assertContains(response, "13:20⚡")

    def test_blend(self):
        service = Service(line_name="X98")
        a = [
            {
                "service": "X98",
                "time": datetime(2017, 4, 21, 20, 10),
                "live": datetime(2017, 4, 21, 20, 2),
            }
        ]
        b = [
            {
                "service": service,
                "time": datetime(2017, 4, 21, 20, 10),
                "live": datetime(2017, 4, 21, 20, 5),
            }
        ]

        live.blend(a, b)
        self.assertEqual(
            a,
            [
                {
                    "service": "X98",
                    "time": datetime(2017, 4, 21, 20, 10),
                    "live": datetime(2017, 4, 21, 20, 5),
                }
            ],
        )

        live.blend(b, a)
        self.assertEqual(
            b,
            [
                {
                    "service": service,
                    "time": datetime(2017, 4, 21, 20, 10),
                    "live": datetime(2017, 4, 21, 20, 5),
                }
            ],
        )

    def test_render(self):
        response = render(
            None,
            "departures.html",
            {
                "departures": [
                    {
                        "time": datetime(1994, 5, 4, 11, 53),
                        "service": "X98",
                        "destination": "Bratislava",
                    },
                    {
                        "time": datetime(1994, 5, 7, 11, 53),
                        "service": "9",
                        "destination": "Shilbottle",
                    },
                ]
            },
        )
        self.assertContains(
            response,
            """
                <h2>Next departures</h2>
                <h3>Wednesday 4 May</h3>
                <table><tbody>
                    <tr><td>X98</td><td>Bratislava</td><td>11:53</td></tr>
                </tbody></table>
                <h3>Saturday 7 May</h3>
                <table><tbody>
                    <tr><td>9</td><td>Shilbottle</td><td>11:53</td></tr>
                </tbody></table>
        """,
            html=True,
        )

    @patch("departures.live.log_vehicle_journey")
    def test_worcestershire(self, mocked_log_vehicle_journey):
        with time_machine.travel("Sat Feb 09 10:45:45 GMT 2019"):
            with vcr.use_cassette("fixtures/vcr/worcester.yaml"):
                with self.assertNumQueries(11):
                    response = self.client.get(self.worcester_stop.get_absolute_url())

        trip_url = f"{self.trip.get_absolute_url()}#stop-time-{self.worcs_stop_time.id}"

        self.assertContains(
            response,
            f"""
            <tr>
                <td>
                    <a href="/services/44">44</a>
                </td>
                <td>Crowngate Bus Station</td>
                <td><a href="{trip_url}">10:54</a></td>
            </tr>
        """,
            html=True,
        )
        self.assertContains(response, "EVESHAM Bus Station")
        self.assertNotContains(response, "WORCESTER")

        args = (
            None,
            {
                "LineRef": "X50",
                "DirectionRef": "O",
                "FramedVehicleJourneyRef": {
                    "DataFrameRef": "2019_02_09_311_4560_220",
                    "DatedVehicleJourneyRef": "311_4560_220",
                },
                "OperatorRef": "FMR",
                "OriginRef": "2000G000106",
                "OriginName": "Crowngate Bus Station",
                "DestinationRef": "2000G000400",
                "DestinationName": "EVESHAM Bus Station",
                "OriginAimedDepartureTime": "2019-02-09T12:10:00Z",
                "Monitored": "true",
                "Delay": "PT0M0S",
                "VehicleRef": "FMR-66692",
                "MonitoredCall": {
                    "AimedDepartureTime": "2019-02-09T12:10:00Z",
                    "ExpectedDepartureTime": "2019-02-09T12:10:00Z",
                    "DepartureStatus": "onTime",
                },
            },
            None,
            "EVESHAM Bus Station",
            "SPT",
            "http://worcestershire-rt-http.trapezenovus.co.uk:8080",
            None,
        )

        # test that the task is called
        mocked_log_vehicle_journey.assert_called_with(*args)
        self.assertEqual(0, VehicleJourney.objects.count())

        # test the actual task
        with self.assertNumQueries(14):
            log_vehicle_journey(*args[:-1], self.trip.id)

        with self.assertNumQueries(3):
            log_vehicle_journey(*args[:-1], self.trip.id)

        Vehicle.objects.update(latest_journey=None)

        with self.assertNumQueries(4):
            log_vehicle_journey(*args[:-1], self.trip.id)

        journey = VehicleJourney.objects.get()
        self.assertEqual(journey.vehicle.latest_journey_data, args[1])
        self.assertEqual(journey.trip, self.trip)
        self.assertEqual(str(journey.datetime), "2019-02-09 12:10:00+00:00")

import zipfile
import datetime
from ciso8601 import parse_datetime
from tempfile import TemporaryDirectory
from pathlib import Path
from vcr import use_cassette
from unittest.mock import patch
import time_machine
from django.test import TestCase, override_settings
from django.core.management import call_command
from busstops.models import (
    Region,
    Operator,
    DataSource,
    OperatorCode,
    Service,
    ServiceCode,
    StopPoint,
    StopArea,
    AdminArea,
)
from vehicles.models import VehicleJourney
from ...models import (
    Route,
    BankHoliday,
    CalendarBankHoliday,
    BankHolidayDate,
    VehicleType,
    Block,
    Garage,
    RouteLink,
    TimetableDataSource,
)


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


class MockZipFile:
    def __init__(self):
        pass


class ImportBusOpenDataTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        ea = Region.objects.create(pk="EA", name="East Anglia")
        lynx = Operator.objects.create(noc="LYNX", region=ea, name="Lynx")
        scpb = Operator.objects.create(
            noc="SCCM", region=ea, name="Stagecoach East", parent="Stagecoach"
        )
        schu = Operator.objects.create(
            noc="SCHU", region=ea, name="Huntingdon", parent="Stagecoach"
        )
        source = DataSource.objects.create(name="National Operator Codes")
        OperatorCode.objects.bulk_create(
            [
                OperatorCode(operator=lynx, source=source, code="LYNX"),
                OperatorCode(operator=scpb, source=source, code="SCPB"),
                OperatorCode(operator=schu, source=source, code="SCHU"),
                OperatorCode(operator=schu, source=source, code="SCCM"),
            ]
        )

    @use_cassette(str(FIXTURES_DIR / "bod_lynx.yaml"))
    @time_machine.travel(datetime.datetime(2020, 5, 1), tick=False)
    def test_import_bod(self):
        admin_area = AdminArea.objects.create(
            id=91, atco_code="290", name="Norfolk", region_id="EA"
        )
        stop_area = StopArea.objects.create(id="", active=True, admin_area=admin_area)
        StopPoint.objects.bulk_create(
            [
                StopPoint(
                    atco_code="2900w0321",
                    common_name="Lion Store",
                    indicator="opp",
                    admin_area=admin_area,
                    stop_area=stop_area,
                    active=True,
                ),
                StopPoint(
                    atco_code="2900w0322",
                    common_name="Lion Store",
                    indicator="adj",
                    admin_area=admin_area,
                    stop_area=stop_area,
                    active=True,
                ),
                StopPoint(
                    atco_code="2900W0314",
                    common_name="Holt Court",
                    indicator="opp",
                    admin_area=admin_area,
                    stop_area=stop_area,
                    active=True,
                ),
                StopPoint(
                    atco_code="2900K132",
                    common_name="Kings Lynn Transport Interchange",
                    admin_area=admin_area,
                    stop_area=stop_area,
                    active=True,
                ),
            ]
        )

        source = TimetableDataSource.objects.create(name="LYNX", search="LYNX")
        source.operators.add("LYNX")

        with TemporaryDirectory() as directory:
            with override_settings(DATA_DIR=Path(directory)):
                call_command("import_bod", "0123456789abc19abc190123456789abc19abc19")

                with self.assertNumQueries(7):
                    call_command(
                        "import_bod", "0123456789abc19abc190123456789abc19abc19"
                    )

                route = Route.objects.get()

                response = self.client.get(route.get_absolute_url())
                self.assertEqual(200, response.status_code)

        self.assertEqual(route.source.name, "Lynx_Clenchwarton_54_20200330")
        self.assertEqual(
            route.source.url,
            "https://data.bus-data.dft.gov.uk/category/dataset/35/download/",
        )
        self.assertEqual(route.source.sha1, "a5eaa3ef8ddefd702833d52d0148adfa0a504e9a")

        self.assertEqual(route.code, "")
        self.assertEqual(route.service_code, "54")

        with self.assertNumQueries(5):
            response = self.client.get(f"/services/{route.service_id}.json")
        self.assertTrue(response.json()["geometry"])

        self.assertFalse(route.service.public_use)

        # a TicketMachineServiceCode should have been created
        service_code = ServiceCode.objects.get()
        self.assertEqual(service_code.code, "1")
        self.assertEqual(service_code.scheme, "SIRI")

        response = self.client.get(f"/services/{route.service_id}/timetable")

        self.assertContains(
            response,
            """
            <tr>
                <th class="stop-name" scope="row">
                    <a href="/stops/2900w0321">Lion Store (opp)</a>
                </th>
                <td>12:19</td>
            </tr>""",
            html=True,
        )

        self.assertContains(
            response,
            "Timetable data from "
            '<a href="https://data.bus-data.dft.gov.uk/category/dataset/35/">Lynx/Bus Open Data Service</a>, '
            "1 April 2020.",
        )

        # test views:

        trip = route.trip_set.first()

        response = self.client.get(f"/trips/{trip.id}.json")
        self.assertEqual(27, len(response.json()["times"]))

        response = self.client.get(trip.get_absolute_url())

        self.assertContains(
            response,
            """<tr class="minor">
            <td class="stop-name">
                Clenchwarton Post Box (adj)
            </td>
            <td>
                09:33
            </td>
        </tr>""",
            html=True,
        )

        expected_json = {
            "times": [
                {
                    "service": {
                        "line_name": "54",
                        "operators": [{"id": "LYNX", "name": "Lynx", "parent": ""}],
                    },
                    "trip_id": trip.id,
                    "destination": {
                        "atco_code": "2900K132",
                        "name": "Kings Lynn Transport Interchange",
                    },
                    "aimed_arrival_time": None,
                    "aimed_departure_time": "2020-05-01T09:15:00+01:00",
                }
            ]
        }

        with self.assertNumQueries(6):
            response = self.client.get("/stops/2900W0321/times.json")
        self.assertEqual(response.json(), expected_json)

        with self.assertNumQueries(6):
            response = self.client.get(
                "/stops/2900W0321/times.json?when=2020-05-01T09:15:00%2b01:00"
            )
        self.assertEqual(response.json(), expected_json)

        with self.assertNumQueries(6):
            response = self.client.get(
                "/stops/2900W0321/times.json?when=2020-05-01T09:15:00"
            )
        self.assertEqual(response.json(), expected_json)

        with self.assertNumQueries(6):
            response = self.client.get("/stops/2900W0321/times.json?limit=10")
        self.assertEqual(1, len(response.json()["times"]))

        with self.assertNumQueries(1):
            response = self.client.get("/stops/2900W0321/times.json?limit=nine")
        self.assertEqual(400, response.status_code)

        with self.assertNumQueries(1):
            response = self.client.get("/stops/2900W0321/times.json?when=yesterday")
        self.assertEqual(400, response.status_code)

        with self.assertNumQueries(10):
            response = self.client.get("/stops/2900W0321?date=2020-05-02")
        self.assertContains(response, "<h3>Monday 4 May</h3>")
        self.assertContains(response, "<h3>Tuesday 5 May</h3>")
        self.assertEqual(str(response.context["when"]), "2020-05-02 00:00:00")

        self.assertContains(response, "Nearby stops")  # other stop in StopArea
        self.assertContains(response, "<small>54</small>")

        with self.assertNumQueries(10):
            response = self.client.get("/stops/2900W0321?date=2020-05-02&time=11:00")
        self.assertEqual(str(response.context["when"]), "2020-05-02 11:00:00")
        self.assertContains(response, "<h3>Tuesday 5 May</h3>")

        with self.assertNumQueries(12):
            response = self.client.get("/stops/2900W0321?date=poop")
        self.assertEqual(str(response.context["when"]), "2020-05-01 01:00:00+01:00")

        with self.assertNumQueries(10):
            response = self.client.get("/stops/2900W0321?date=2020-05-02")
        self.assertEqual(str(response.context["when"]), "2020-05-02 00:00:00")

        # test get_trip
        journey = VehicleJourney(
            datetime=parse_datetime("2020-11-02T15:07:06+00:00"),
            service=Service.objects.get(),
            code="1",
            source=route.source,
        )
        journey.trip = journey.get_trip()
        self.assertEqual(journey.trip.ticket_machine_code, "1")
        journey.save()  # for use later

        journey.code = "0915"
        trip = journey.get_trip()
        self.assertEqual(trip.ticket_machine_code, "1")

        trip = journey.get_trip(destination_ref="290J34")
        self.assertIsNone(trip)

        trip = journey.get_trip(destination_ref="2900K132")
        self.assertEqual(trip.ticket_machine_code, "1")

        journey.code = "0916"
        trip = journey.get_trip()
        self.assertIsNone(trip)

        trip = journey.get_trip(destination_ref="2900K132")
        self.assertIsNone(trip)

        # test trip copy:
        trip = route.trip_set.first()
        trip.copy(datetime.timedelta(hours=1))

        # test journey with trip json
        with patch("vehicles.views.redis_client.lrange") as mock_lrange:
            mock_lrange.return_value = []
            response = self.client.get(f"/journeys/{journey.id}.json")
            json = response.json()
            self.assertIn("stops", json)
            self.assertNotIn("locations", json)

            # journey locations but no stop locations
            mock_lrange.return_value = [
                b'["2019-05-29T13:03:34+01:00", [0.23, 52.729], null, null]'
            ]
            response = self.client.get(f"/journeys/{journey.id}.json")
            json = response.json()
            self.assertIn("stops", json)
            self.assertIn("locations", json)

            # journey locations and stop location
            StopPoint.objects.filter(atco_code="2900W0314").update(
                latlong="POINT(0.23 52.729)"
            )
            response = self.client.get(f"/journeys/{journey.id}.json")
            json = response.json()
            self.assertEqual(
                json["stops"][2]["actual_departure_time"], "2019-05-29T13:03:34+01:00"
            )

    def test_ticketer(self):
        source = TimetableDataSource.objects.create(
            name="Completely Coach Travel",
            region_id="EA",
            url="https://opendata.ticketer.com/uk/Completely_Coach_Travel/routes_and_timetables/current.zip",
        )

        with TemporaryDirectory() as directory:
            with override_settings(DATA_DIR=Path(directory)):
                with use_cassette(str(FIXTURES_DIR / "bod_ticketer.yaml")):
                    with self.assertLogs(
                        "bustimes.management.commands.import_transxchange",
                        "WARNING",
                    ) as cm:
                        call_command("import_bod", "ticketer")

                    with self.assertNumQueries(2):
                        call_command("import_bod", "ticketer")  # not modified

                    with self.assertNumQueries(1):
                        call_command(
                            "import_bod", "ticketer", "POOP"
                        )  # no matching setting

                source = DataSource.objects.get(name="Completely Coach Travel")
                service = source.service_set.first()
                route = service.route_set.first()

                response = self.client.get(route.get_absolute_url())
                self.assertEqual(response.status_code, 200)

        response = self.client.get(service.get_absolute_url())
        self.assertContains(
            response,
            "Timetable data from "
            "https://opendata.ticketer.com/uk/Completely_Coach_Travel/routes_and_timetables/current.zip, "
            "24 September 2021",
        )

        self.assertEqual(
            cm.output,
            [
                "WARNING:bustimes.management.commands.import_transxchange:{'NationalOperatorCode': 'CPLT', "
                "'OperatorShortName': 'Completely Coach Travel', 'LicenceNumber': 'PF2024545'}"
            ],
        )

    @time_machine.travel(datetime.datetime(2020, 6, 10))
    def test_import_stagecoach(self):

        source = TimetableDataSource.objects.create(
            name="Stagecoach East",
            region_id="EA",
            url="https://opendata.stagecoachbus.com/stagecoach-sccm-route-schedule-data-transxchange.zip",
        )
        source.operators.add("SCCM")

        StopPoint.objects.bulk_create(
            [
                StopPoint(
                    atco_code="0500HYAXL033",
                    common_name="Folly Close",
                    indicator="opp",
                    active=True,
                ),
                StopPoint(
                    atco_code="0500HYAXL007",
                    common_name="Motel",
                    indicator="opp",
                    active=True,
                ),
                StopPoint(
                    atco_code="0500HFOLK002",
                    common_name="Folksworth Road",
                    indicator="opp",
                    active=True,
                ),
                StopPoint(
                    atco_code="0500HSTIV054",
                    common_name="St John's Road",
                    indicator="opp",
                    active=True,
                ),
                StopPoint(
                    atco_code="0500HHUNT049",
                    common_name="Church Lane",
                    indicator="near",
                    active=True,
                ),
            ]
        )

        with TemporaryDirectory() as directory:
            with override_settings(DATA_DIR=Path(directory)):
                for archive_name in (
                    "stagecoach-sccm-route-schedule-data-transxchange.zip",
                    "stagecoach-sccm-route-schedule-data-transxchange_2_4.zip",
                ):
                    path = Path(directory) / archive_name

                    with zipfile.ZipFile(path, "a") as open_zipfile:
                        for filename in (
                            "904_FE_PF_904_20210102.xml",
                            "904_VI_PF_904_20200830.xml",
                        ):
                            open_zipfile.write(FIXTURES_DIR / filename, filename)

                with patch(
                    "bustimes.management.commands.import_bod.download_if_changed",
                    return_value=(True, parse_datetime("2020-06-10T12:00:00+01:00")),
                ) as download_if_changed:
                    with self.assertNumQueries(153):
                        call_command("import_bod", "stagecoach")
                    download_if_changed.assert_called_with(
                        path, "https://opendata.stagecoachbus.com/" + archive_name
                    )

                    route_links = RouteLink.objects.order_by("id")
                    self.assertEqual(len(route_links), 2)
                    route_link = route_links[0]
                    route_link.geometry = (
                        "SRID=4326;LINESTRING(0 0, 0 0)"  # should be overwritten later
                    )
                    route_link.save()

                    with self.assertNumQueries(6):
                        call_command("import_bod", "stagecoach")

                    with self.assertNumQueries(1):
                        call_command("import_bod", "stagecoach", "SCOX")

                    with self.assertNumQueries(95):
                        call_command("import_bod", "stagecoach", "SCCM")

                    route_link.refresh_from_db()
                    self.assertEqual(len(route_link.geometry.coords), 32)

                source = DataSource.objects.filter(name="Stagecoach East").first()
                response = self.client.get(f"/sources/{source.id}/routes/")

                self.assertEqual(
                    response.content.decode(),
                    "904_FE_PF_904_20210102.xml\n904_VI_PF_904_20200830.xml",
                )

                route = Route.objects.first()
                response = self.client.get(route.get_absolute_url())
                self.assertEqual(200, response.status_code)
                self.assertEqual("", response.filename)

        self.assertEqual(BankHoliday.objects.count(), 13)
        self.assertEqual(CalendarBankHoliday.objects.count(), 130)
        self.assertEqual(VehicleType.objects.count(), 3)
        self.assertEqual(Garage.objects.count(), 4)
        self.assertEqual(Block.objects.count(), 12)

        with self.assertNumQueries(5):
            response = self.client.get(f"/services/{route.service_id}.json")
        self.assertTrue(response.json()["geometry"])

        self.assertEqual(1, Service.objects.count())
        self.assertEqual(2, Route.objects.count())

        with self.assertNumQueries(16):
            response = self.client.get("/services/904-huntingdon-peterborough")
        self.assertContains(
            response,
            '<option selected value="2020-08-31">Monday 31 August 2020</option>',
        )
        self.assertContains(response, '<a href="/operators/huntingdon">Huntingdon</a>')

        with time_machine.travel("2021-01-11"):
            response = self.client.get("/services/904-huntingdon-peterborough")
        self.assertContains(
            response,
            "The timetable data for this service was valid until Sunday 10 January 2021. But",
        )

        BankHolidayDate.objects.create(
            bank_holiday=BankHoliday.objects.get(name="ChristmasDay"), date="2020-12-25"
        )
        with self.assertNumQueries(14):
            response = self.client.get(
                "/services/904-huntingdon-peterborough?date=2020-12-25"
            )
            self.assertContains(
                response, "Sorry, no journeys found for Friday 25 December 2020"
            )

import time_machine
from pathlib import Path
from django.core.cache import cache
from vcr import use_cassette
from django.test import TestCase, override_settings
from busstops.models import (
    Region,
    DataSource,
    Operator,
    OperatorCode,
    StopPoint,
    Locality,
    AdminArea,
    Service,
)
from bustimes.models import Route, Trip
from ...models import VehicleLocation, VehicleJourney, Vehicle
from ...workers import SiriConsumer
from ...utils import flush_redis
from ..commands import import_bod_avl, import_bod_avl_channels


class BusOpenDataVehicleLocationsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        region = Region.objects.create(id="EA")
        Operator.objects.bulk_create(
            [
                Operator(id="WHIP", region=region),
                Operator(id="TGTC", region=region),
                Operator(id="HAMS", region=region),
                Operator(id="UNOE", region=region),
                Operator(id="UNIB", region=region),
                Operator(id="FBRI", region=region, parent="First"),
                Operator(id="FECS", region=region, parent="First"),
                Operator(id="NCTP", region=region),
            ]
        )
        Vehicle.objects.bulk_create(
            [
                Vehicle(operator_id="NCTP", code="2929", name="Jeff"),
                Vehicle(operator_id="FECS", code="11111"),
            ]
        )
        cls.source = DataSource.objects.create(
            name="Bus Open Data",
            url="https://data.bus-data.dft.gov.uk/api/v1/datafeed/",
        )
        OperatorCode.objects.bulk_create(
            [
                OperatorCode(operator_id="HAMS", source=cls.source, code="HAMSTRA"),
                OperatorCode(operator_id="TGTC", source=cls.source, code="FOO"),
                OperatorCode(operator_id="WHIP", source=cls.source, code="FOO"),
                OperatorCode(operator_id="UNOE", source=cls.source, code="UNOE"),
                OperatorCode(operator_id="UNOE", source=cls.source, code="UNIB"),
            ]
        )

        suffolk = AdminArea.objects.create(
            region=region, id=1, atco_code=390, name="Suffolk"
        )
        southwold = Locality.objects.create(admin_area=suffolk, name="Southwold")
        StopPoint.objects.create(
            atco_code="390071066",
            locality=southwold,
            active=True,
            common_name="Kings Head",
        )
        StopPoint.objects.create(atco_code="0500CCITY544", active=False)

        service_u = Service.objects.create(line_name="U")
        service_u.operator.add("WHIP")
        cls.service_c = Service.objects.create(line_name="c")
        cls.service_c.operator.add("HAMS")
        route_u = Route.objects.create(service=service_u, source=cls.source, code="u", line_name="UU")
        # route_c = Route.objects.create(service=service_c, source=cls.source, code='c')
        Trip.objects.create(
            route=route_u,
            start="09:23:00",
            end="10:50:00",
            destination_id="0500CCITY544",
        )
        # calendar = Calendar.objects.create(mon=True, tue=True, wed=True, thu=True,
        #                                    fri=True, sat=True, sun=True, start_date='2020-10-20')
        # Trip.objects.create(route=route_c, start='15:32:00', end='23:00:00', calendar=calendar)

    def test_get_operator(self):
        command = import_bod_avl_channels.Command()
        command.source = self.source

        self.assertEqual(command.get_operator("HAMS").get().id, "HAMS")
        self.assertEqual(command.get_operator("HAMSTRA").get().id, "HAMS")
        self.assertEqual(command.get_operator("UNOE").get().id, "UNOE")

        # should ignore operator with id 'UNIB' in favour of one with OperatorCode:
        self.assertEqual(command.get_operator("UNIB").get().id, "UNOE")

        self.assertEqual(
            list(command.get_operator("FOO").values("id")),
            [{"id": "WHIP"}, {"id": "TGTC"}],
        )

    @time_machine.travel("2020-05-01", tick=False)
    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    )
    def test_channels_update(self):
        command = import_bod_avl_channels.Command()
        command.source = self.source

        with use_cassette(
            str(Path(__file__).resolve().parent / "vcr" / "bod_avl.yaml")
        ) as cassette:
            command.update()

            cassette.rewind()

            command.update()

        self.assertEqual(841, len(command.identifiers))

        response = self.client.get("/status")
        self.assertContains(
            response,
            """
            <tr>
                <td>00:00:00.000000</td>
                <td>15:14:46.261274</td>
                <td>841</td>
                <td>841</td>
            </tr>""",
        )
        self.assertContains(
            response,
            """
            <tr>
                <td>00:00:00.000000</td>
                <td>15:14:46.261274</td>
                <td>841</td>
                <td>0</td>
            </tr>""",
        )

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    )
    def test_task(self):
        flush_redis()

        items = [
            {
                "RecordedAtTime": "2020-10-17T08:34:00+00:00",
                "ItemIdentifier": "13505681-c482-451d-a089-ee805e196e7e",
                "ValidUntilTime": "2020-10-24T14:19:46.982911",
                "MonitoredVehicleJourney": {
                    "LineRef": "U",
                    "DirectionRef": "INBOUND",
                    "PublishedLineName": "U",
                    "OperatorRef": "WHIP",
                    "OriginRef": "0500CCITY536",
                    "OriginName": "Dame Mary Archer Wa",
                    "DestinationRef": "0500CCITY544",
                    "DestinationName": "Eddington Sainsbury",
                    "OriginAimedDepartureTime": "2020-06-17T08:23:00+00:00",
                    "VehicleLocation": {
                        "Longitude": "0.141533",
                        "Latitude": "52.1727219",
                        "VehicleJourneyRef": "UNKNOWN",
                    },
                    "VehicleRef": "WHIP-106",
                },
            },
            {
                "ItemIdentifier": "3d723567-dbd6-424c-a3e5-8bbc4932c8b8",
                "RecordedAtTime": "2020-10-30T05:06:29+00:00",
                "ValidUntilTime": "2020-10-30T05:11:31.887243",
                "MonitoredVehicleJourney": {
                    "LineRef": "TGTC:PD1050400:19:242",
                    "PublishedLineName": "843X",
                    "OriginRef": "43000575801",
                    "OriginName": "843X Roughley",
                    "VehicleRef": "SN56 AFE",
                    "OperatorRef": "TGTC",
                    "DestinationRef": "43000280301",
                    "DestinationName": "843X Soho Road",
                    "VehicleLocation": {
                        "Latitude": "52.4972115",
                        "Longitude": "-1.9283381",
                    },
                },
            },
            {
                "ItemIdentifier": "87043019-595c-4269-b4de-a359ae17a474",
                "RecordedAtTime": "2020-10-15T07:46:08+00:00",
                "ValidUntilTime": "2020-10-15T18:02:11.033673",
                "MonitoredVehicleJourney": {
                    "LineRef": "C",
                    "BlockRef": "503",
                    "VehicleRef": "DW18-HAM",
                    "OperatorRef": "HAMSTRA",
                    "DirectionRef": "outbound",
                    "DestinationRef": "2400103099",
                    "VehicleLocation": {"Latitude": "51.2135", "Longitude": "0.285348"},
                    "Bearing": "92.0",
                    "PublishedLineName": "C",
                    "VehicleJourneyRef": "C_20201015_05_53",
                },
                "Extensions": {
                    "VehicleJourney": {
                        "DriverRef": "1038",
                        "Operational": {
                            "TicketMachine": {
                                "JourneyCode": "1532",
                                "TicketMachineServiceCode": "258",
                            }
                        },
                        "VehicleUniqueId": "T2-1",
                    }
                },
            },
        ]

        consumer = SiriConsumer()
        with self.assertNumQueries(36):
            consumer.sirivm({"when": "2020-10-15T07:46:08+00:00", "items": items})
        with self.assertNumQueries(1):
            consumer.sirivm({"when": "2020-10-15T07:46:08+00:00", "items": items})

        self.assertEqual(3, VehicleLocation.objects.all().count())

        location = VehicleLocation.objects.all()[1]
        self.assertEqual(location.journey.route_name, "843X")
        self.assertEqual(location.journey.destination, "Soho Road")
        self.assertEqual(location.journey.vehicle.reg, "SN56AFE")

        location = VehicleLocation.objects.all()[2]
        self.assertEqual(location.heading, 92)
        self.assertEqual(location.journey.vehicle.operator_id, "HAMS")
        self.assertEqual(location.journey.vehicle.reg, "DW18HAM")
        self.assertEqual(location.journey.vehicle.reg, "DW18HAM")

        # test operator map
        with self.assertNumQueries(1):
            response = self.client.get("/vehicles.json?operator=HAMS")
        json = response.json()
        self.assertEqual(
            json,
            [
                {
                    "id": location.id,
                    "coordinates": [0.285348, 51.2135],
                    "vehicle": {
                        "url": f"/vehicles/{location.vehicle.id}",
                        "name": "T2-1 - DW18 HAM",
                    },
                    "heading": 92.0,
                    "datetime": "2020-10-15T07:46:08Z",
                    "destination": "",
                    "service_id": self.service_c.id,
                    "service": {"line_name": "c", "url": "/services/c"},
                }
            ],
        )

        response = self.client.get("/operators/hams/map")
        self.assertContains(response, 'OPERATOR_ID="HAMS";')
        self.assertContains(response, "/operators/hams/map")

        # test other maps
        with self.assertNumQueries(1):
            response = self.client.get(f"/vehicles.json?service={self.service_c.id},-2")
        self.assertEqual(response.json(), json)

        with self.assertNumQueries(1):
            response = self.client.get("/vehicles.json")
        self.assertEqual(len(response.json()), 3)

        with self.assertNumQueries(1):
            response = self.client.get("/vehicles.json?service__isnull=True")
        self.assertEqual(len(response.json()), 1)

        with self.assertNumQueries(0):
            response = self.client.get("/vehicles.json?service=ff")
        self.assertEqual(response.status_code, 400)

        # test cache
        self.assertIs(False, cache.get("TGTC:843X:43000280301"))
        self.assertIsNone(cache.get("HAMS:C:2400103099"))
        self.assertIsNone(cache.get("WHIP:U:0500CCITY544"))

        # test history view
        whippet_journey = VehicleJourney.objects.get(vehicle__operator="WHIP")
        response = self.client.get(whippet_journey.get_absolute_url())
        self.assertContains(
            response, '<a href="/services/u/vehicles?date=2020-06-17">UU</a>'
        )
        self.assertContains(
            response,
            f'<td colspan="2"><a href="/trips/{whippet_journey.trip_id}">09:23</a></td>',
        )

    def test_handle_item(self):
        command = import_bod_avl.Command()
        command.source = self.source

        flush_redis()

        command.handle_item(
            {
                "Extensions": {
                    "VehicleJourney": {"DriverRef": "105", "VehicleUniqueId": "104"}
                },
                "ItemIdentifier": "2cb5543a-add1-4e14-ae7a-a1ee730d9814",
                "RecordedAtTime": "2020-11-28T12:58:25+00:00",
                "ValidUntilTime": "2020-11-28T13:04:06.989808",
                "MonitoredVehicleJourney": {
                    "LineRef": "146",
                    "BlockRef": "2",
                    "VehicleRef": "BB62_BUS",
                    "OperatorRef": "BDRB",
                    "DirectionRef": "inbound",
                    "VehicleLocation": {
                        "Latitude": "52.62269",
                        "Longitude": "1.296443",
                    },
                    "PublishedLineName": "146",
                    "VehicleJourneyRef": "146_20201128_12_58",
                },
            }
        )
        command.save()
        command.handle_item(
            {
                "RecordedAtTime": "2020-11-28T15:07:06+00:00",
                "ItemIdentifier": "26ff29be-0d0a-4f5e-8160-bec0d831b681",
                "ValidUntilTime": "2020-11-28T15:12:56.049069",
                "MonitoredVehicleJourney": {
                    "LineRef": "146",
                    "DirectionRef": "inbound",
                    "PublishedLineName": "146",
                    "OperatorRef": "BDRB",
                    "DestinationRef": "390071066",
                    "VehicleLocation": {
                        "Longitude": "1.675893",
                        "Latitude": "52.328398",
                    },
                    "BlockRef": "2",
                    "VehicleJourneyRef": "146_20201128_12_58",
                    "VehicleRef": "BB62_BUS",
                },
            }
        )
        command.save()

        journey = VehicleJourney.objects.get()
        self.assertEqual(journey.direction, "inbound")
        self.assertEqual(journey.destination, "Southwold")

        with self.assertNumQueries(1):
            response = self.client.get(f"/journeys/{journey.id}.json")
        self.assertEqual(
            response.json(),
            {
                "locations": [
                    {
                        "coordinates": [1.296443, 52.62269],
                        "datetime": "2020-11-28T12:58:25Z",
                        "delta": None,
                        "direction": None,
                    },
                    {
                        "coordinates": [1.675893, 52.328398],
                        "datetime": "2020-11-28T15:07:06Z",
                        "delta": None,
                        "direction": 142,
                    },
                ]
            },
        )

        vehicle = journey.vehicle
        location = VehicleLocation.objects.get()

        with self.assertNumQueries(6):
            response = self.client.get(journey.get_absolute_url())
        self.assertContains(response, "146")
        self.assertContains(response, "to Southwold")
        self.assertContains(
            response, f'<td><a href="#journeys/{journey.id}">Map</a></td>'
        )

        with self.assertNumQueries(0):
            response = self.client.get(
                "/vehicles.json?xmax=984.375&xmin=694.688&ymax=87.043&ymin=-89.261"
            )
        self.assertEqual(response.status_code, 400)

        with self.assertNumQueries(0):
            response = self.client.get(
                "/vehicles.json?ymax=52.3&xmax=1.7&ymin=52.3&xmin=1.6"
            )
        self.assertEqual(response.json(), [])

        with self.assertNumQueries(1):
            response = self.client.get(
                "/vehicles.json?ymax=52.4&xmax=1.7&ymin=52.3&xmin=1.6"
            )
        self.assertEqual(
            response.json(),
            [
                {
                    "id": location.id,
                    "coordinates": [1.675893, 52.328398],
                    "vehicle": {
                        "url": f"/vehicles/{vehicle.id}",
                        "name": "104 - BB62 BUS",
                    },
                    "heading": 142,
                    "datetime": "2020-11-28T15:07:06Z",
                    "destination": "Southwold",
                    "service": {"line_name": "146"},
                }
            ],
        )

        with self.assertNumQueries(1):
            response = self.client.get("/vehicles.json")
        self.assertEqual(
            response.json(),
            [
                {
                    "id": location.id,
                    "coordinates": [1.675893, 52.328398],
                    "vehicle": {
                        "url": f"/vehicles/{vehicle.id}",
                        "name": "104 - BB62 BUS",
                    },
                    "heading": 142,
                    "datetime": "2020-11-28T15:07:06Z",
                    "destination": "Southwold",
                    "service": {"line_name": "146"},
                }
            ],
        )

    def test_units(self):
        command = import_bod_avl.Command()
        command.source = self.source
        item = {
            "Extensions": {
                "VehicleJourney": {
                    "DriverRef": "65559",
                    "Operational": {
                        "TicketMachine": {
                            "JourneyCode": "1215",
                            "TicketMachineServiceCode": "m1",
                        }
                    },
                    "VehicleUniqueId": "2929",
                }
            },
            "ItemIdentifier": "c5da91a4-e7c8-45f2-aedb-1699997282dc",
            "RecordedAtTime": "2021-10-10T10:58:51+00:00",
            "ValidUntilTime": "2021-10-10T11:04:02.957172",
            "MonitoredVehicleJourney": {
                "LineRef": "m1",
                "BlockRef": "65559",
                "VehicleRef": "2929",
                "OperatorRef": "FBRI",
                "DirectionRef": "outbound",
                "DestinationRef": "010000008",
                "VehicleLocation": {"Latitude": "51.527146", "Longitude": "-2.596353"},
                "PublishedLineName": "m1",
                "VehicleJourneyRef": "m1_20211010_10_58",
            },
        }
        vehicle, created = command.get_vehicle(item)
        self.assertFalse(created)
        self.assertEqual(vehicle.name, "Jeff")

        journey = command.get_journey(item, vehicle)
        self.assertEqual("1215", journey.code)
        self.assertEqual("outbound", journey.direction)

        item["MonitoredVehicleJourney"]["VehicleRef"] = "11111"
        vehicle, created = command.get_vehicle(item)
        self.assertFalse(created)
        self.assertEqual(vehicle.code, "11111")
        # self.assertEqual(vehicle.fleet_code, "2929")

        item["MonitoredVehicleJourney"]["VehicleRef"] = "FBRI-502_-_DK09_DZH"
        vehicle, created = command.get_vehicle(item)
        self.assertTrue(created)

        self.assertEqual("DK09DZH", vehicle.reg)
        self.assertEqual("502_-_DK09_DZH", vehicle.code)
        self.assertEqual("502", vehicle.fleet_code)
        self.assertEqual("502", vehicle.fleet_number)

    @time_machine.travel("2021-03-05T14:20:40+00:00")
    def test_handle_extensions(self):
        command = import_bod_avl.Command()
        command.source = self.source

        flush_redis()

        command.handle_item(
            {
                "Extensions": {
                    "VehicleJourney": {
                        "DriverRef": "98119",
                        "Operational": {
                            "TicketMachine": {
                                "JourneyCode": "1426",
                                "TicketMachineServiceCode": "42",
                            }
                        },
                        "SeatedCapacity": "27",
                        "SeatedOccupancy": "0",
                        "VehicleUniqueId": "626",
                        "WheelchairCapacity": "1",
                        "OccupancyThresholds": "14,16",
                        "WheelchairOccupancy": "0",
                    }
                },
                "ItemIdentifier": "4f61f0ab-0976-41e1-a899-044bb78618e4",
                "RecordedAtTime": "2021-03-05T14:26:43+00:00",
                "ValidUntilTime": "2021-03-05T14:32:12.638839",
                "MonitoredVehicleJourney": {
                    "Bearing": "189.0",
                    "LineRef": "42",
                    "BlockRef": "52",
                    "Occupancy": "seatsAvailable",
                    "VehicleRef": "626",
                    "OperatorRef": "GNEL",
                    "DirectionRef": "inbound",
                    "DestinationRef": "41000010WALB",
                    "VehicleLocation": {
                        "Latitude": "55.084628",
                        "Longitude": "-1.586568",
                    },
                    "PublishedLineName": "42",
                    "VehicleJourneyRef": "4237",
                },
            }
        )

        command.save()

        location = VehicleLocation.objects.get()

        response = self.client.get("/vehicles.json")
        self.assertEqual(
            response.json(),
            [
                {
                    "id": location.id,
                    "coordinates": [-1.586568, 55.084628],
                    "vehicle": {
                        "url": f"/vehicles/{location.vehicle.id}",
                        "name": "626",
                    },
                    "heading": 189.0,
                    "datetime": "2021-03-05T14:26:43Z",
                    "destination": "",
                    "service": {"line_name": "42"},
                    "seats": "27 free",
                    "wheelchair": "free",
                }
            ],
        )

    @time_machine.travel("2021-05-08T13:00+00:00")
    def test_invalid_location(self):
        command = import_bod_avl.Command()
        command.source = self.source

        item = {
            "RecordedAtTime": "2021-05-08T12:54:36+00:00",
            "ItemIdentifier": "db82c74d-e2ac-48f4-8963-4cea2d706b6d",
            "ValidUntilTime": "2021-05-08T12:59:47.376621",
            "MonitoredVehicleJourney": {
                "LineRef": "8",
                "DirectionRef": "OUTBOUND",
                "PublishedLineName": "8",
                "OperatorRef": "SCHI",
                "OriginRef": "670030036",
                "OriginName": "Stratton Road",
                "DestinationRef": "670030036",
                "DestinationName": "Stratton Road",
                "OriginAimedDepartureTime": "2021-05-08T12:30:00+00:00",
                "VehicleLocation": {
                    "Longitude": "149.2244263",
                    "Latitude": "87.8245926",
                },
                "Bearing": "0.0",
                "VehicleJourneyRef": "2029",
                "VehicleRef": "SCHI-21210",
            },
            "Extensions": None,
        }
        command.handle_item(item)
        command.save()

        journey = VehicleJourney.objects.get()
        self.assertEqual(item, journey.data)

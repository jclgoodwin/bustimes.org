import os
import redis
import time_machine
from django.core.cache import cache
from mock import patch
from vcr import use_cassette
from django.conf import settings
from django.test import TestCase, override_settings
from busstops.models import Region, DataSource, Operator, OperatorCode, StopPoint, Locality, AdminArea
from ...models import VehicleLocation, VehicleJourney
from ...tasks import bod_avl
from ..commands import import_bod_avl, import_bod_avl_celery, import_bod_avl_channels

DIR = os.path.dirname(os.path.abspath(__file__))


class BusOpenDataVehicleLocationsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        region = Region.objects.create(id='EA')
        Operator.objects.bulk_create([
            Operator(id='WHIP', region=region),
            Operator(id='TGTC', region=region),
            Operator(id='HAMS', region=region),
        ])
        cls.source = DataSource.objects.create(
            name='Bus Open Data',
            url='https://data.bus-data.dft.gov.uk/api/v1/datafeed/'
        )
        OperatorCode.objects.create(operator_id='HAMS', source=cls.source, code='HAMSTRA')

        suffolk = AdminArea.objects.create(region=region, id=1, atco_code=390, name='Suffolk')
        southwold = Locality.objects.create(admin_area=suffolk, name='Southwold')
        StopPoint.objects.create(atco_code='390071066', locality=southwold, active=True, common_name='Kings Head')

    @time_machine.travel('2020-05-01')
    @override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
    def test_channels_update(self):
        command = import_bod_avl_channels.Command()
        command.source = self.source

        with use_cassette(os.path.join(DIR, 'vcr', 'bod_avl.yaml')):
            command.update()

        with use_cassette(os.path.join(DIR, 'vcr', 'bod_avl.yaml')):
            command.update()

        self.assertEqual(841, len(command.identifiers))

        response = self.client.get('/status')
        self.assertContains(response, """
            <tr>
                <td>24 Jul 15:14:46</td>
                <td>841</td>
                <td>841</td>
            </tr>""")
        self.assertContains(response, """
            <tr>
                <td>24 Jul 15:14:46</td>
                <td>841</td>
                <td>0</td>
            </tr>""")

    def test_celery_update(self):
        command = import_bod_avl_celery.Command()
        with patch('vehicles.management.commands.import_bod_avl.Command.get_items', return_value=[]):
            self.assertEqual(300, command.update())

    @override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
    def test_task(self):
        r = redis.from_url(settings.REDIS_URL)
        r.flushall()

        items = [{
            'RecordedAtTime': '2020-06-17T08:34:00+00:00',
            'ItemIdentifier': '13505681-c482-451d-a089-ee805e196e7e',
            'ValidUntilTime': '2020-07-24T14:19:46.982911',
            'MonitoredVehicleJourney': {
                'LineRef': 'U',
                'DirectionRef': 'INBOUND',
                'PublishedLineName': 'U',
                'OperatorRef': 'WHIP',
                'OriginRef': '0500CCITY536',
                'OriginName': 'Dame Mary Archer Wa',
                'DestinationRef': '0500CCITY544',
                'DestinationName': 'Eddington Sainsbury',
                'OriginAimedDepartureTime': '2020-06-17T08:23:00+00:00',
                'VehicleLocation': {
                    'Longitude': '0.141533',
                    'Latitude': '52.1727219',
                    'VehicleJourneyRef': 'UNKNOWN',
                },
                'VehicleRef': 'WHIP-106'
            }
        }, {
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
                    "Longitude": "-1.9283381"
                }
            }
        }, {
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
                "VehicleLocation": {
                    "Latitude": "51.2135",
                    "Longitude": "0.285348"
                },
                "Bearing": "92.0",
                "PublishedLineName": "C",
                "VehicleJourneyRef": "C_20201015_05_53"
            }
        }]

        with self.assertNumQueries(29):
            bod_avl(items)
        with self.assertNumQueries(2):
            bod_avl(items)

        self.assertEqual(3, VehicleLocation.objects.all().count())

        location = VehicleLocation.objects.all()[1]
        self.assertEqual(location.journey.route_name, '843X')
        self.assertEqual(location.journey.destination, 'Soho Road')
        self.assertEqual(location.journey.vehicle.reg, 'SN56AFE')

        location = VehicleLocation.objects.all()[2]
        self.assertEqual(location.heading, 92)
        self.assertEqual(location.journey.vehicle.operator_id, 'HAMS')
        self.assertEqual(location.journey.vehicle.reg, 'DW18HAM')
        self.assertEqual(location.journey.vehicle.reg, 'DW18HAM')

        # test operator map
        with self.assertNumQueries(1):
            response = self.client.get('/vehicles.json?operator=HAMS')
        self.assertEqual(response.json(), [{
            "id": location.id,
            "coordinates": [0.285348, 51.2135],
            "vehicle": {
                "url": f"/vehicles/{location.vehicle.id}",
                "name": "DW18\u00a0HAM"
            },
            "heading": 92.0,
            "datetime": "2020-10-15T07:46:08Z",
            "destination": "",
            "service": {"line_name": "C"}
        }])

        response = self.client.get('/operators/hams/map')
        self.assertContains(response, 'EXTENT = [0.285348,51.2135,0.285348,51.2135];OPERATOR_ID="HAMS";')

        self.assertIs(cache.get('WHIP:U:0500CCITY544'), False)
        self.assertIsNone(cache.get('WHIP:U:0500CCITY5'))

    def test_handle_item(self):
        command = import_bod_avl.Command()
        command.source = self.source

        r = redis.from_url(settings.REDIS_URL)
        r.flushall()

        command.handle_item({
            "Extensions": {
                "VehicleJourney": {
                    "DriverRef": "105",
                    "VehicleUniqueId": "104"
                }
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
                    "Longitude": "1.296443"
                },
                "PublishedLineName": "146",
                "VehicleJourneyRef": "146_20201128_12_58"
            }
        })
        command.save()
        command.handle_item({
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
                "VehicleRef": "BB62_BUS"
            }
        })
        command.save()

        journey = VehicleJourney.objects.get()
        self.assertEqual(journey.direction, 'inbound')
        self.assertEqual(journey.destination, 'Southwold')

        with self.assertNumQueries(1):
            response = self.client.get(f'/journeys/{journey.id}.json')
        self.assertEqual(response.json(), {'locations': [
            {'coordinates': [1.296443, 52.62269],
             'datetime': '2020-11-28T12:58:25Z',
             'delta': None,
             'direction': None},
            {'coordinates': [1.675893, 52.328398],
             'datetime': '2020-11-28T15:07:06Z',
             'delta': None,
             'direction': 142}]})

        vehicle = journey.vehicle
        location = VehicleLocation.objects.get()

        with self.assertNumQueries(0):
            response = self.client.get('/vehicles.json?ymax=52.3&xmax=1.7&ymin=52.3&xmin=1.6')
        self.assertEqual(response.json(), [])

        with self.assertNumQueries(1):
            response = self.client.get('/vehicles.json?ymax=52.4&xmax=1.7&ymin=52.3&xmin=1.6')
        self.assertEqual(response.json(), [
            {'id': location.id, 'coordinates': [1.675893, 52.328398],
             'vehicle': {'url': f'/vehicles/{vehicle.id}', 'name': '104 - BB62\xa0BUS'},
             'heading': 142, 'datetime': '2020-11-28T15:07:06Z', 'destination': 'Southwold',
             'service': {'line_name': '146'}}
        ])

        with self.assertNumQueries(1):
            response = self.client.get('/vehicles.json')
        self.assertEqual(response.json(), [
            {'id': location.id, 'coordinates': [1.675893, 52.328398],
             'vehicle': {'url': f'/vehicles/{vehicle.id}', 'name': '104 - BB62\xa0BUS'},
             'heading': 142, 'datetime': '2020-11-28T15:07:06Z', 'destination': 'Southwold',
             'service': {'line_name': '146'}}
        ])

    @time_machine.travel('2021-03-05T14:20:40+00:00')
    def test_handle_extensions(self):
        command = import_bod_avl.Command()
        command.source = self.source

        r = redis.from_url(settings.REDIS_URL)
        r.flushall()

        command.handle_item({
            "Extensions": {
                "VehicleJourney": {
                    "DriverRef": "98119",
                    "Operational": {
                        "TicketMachine": {
                            "JourneyCode": "1426",
                            "TicketMachineServiceCode": "42"
                        }
                    },
                    "SeatedCapacity": "27",
                    "SeatedOccupancy": "0",
                    "VehicleUniqueId": "626",
                    "WheelchairCapacity": "1",
                    "OccupancyThresholds": "14,16",
                    "WheelchairOccupancy": "0"
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
                    "Longitude": "-1.586568"
                },
                "PublishedLineName": "42",
                "VehicleJourneyRef": "4237"
            }
        })

        command.save()

        location = VehicleLocation.objects.get()

        response = self.client.get('/vehicles.json')
        self.assertEqual(response.json(), [{
            "id": location.id, "coordinates": [-1.586568, 55.084628],
            "vehicle": {
                "url": f"/vehicles/{location.vehicle.id}",
                "name": "626"
            },
            "heading": 189.0,
            "datetime": "2021-03-05T14:26:43Z",
            "destination": "",
            "service": {"line_name": "42"},
            "seats": "27 free",
            "wheelchair": "free",
        }])

        #  BlockRef
        self.assertEqual(location.journey.block, '52')

        # BlockRef same as DriverRef - block is None
        location.journey.data['MonitoredVehicleJourney']['BlockRef'] = '98119'
        del location.journey.block
        self.assertIsNone(location.journey.block)

        # BlockRef same as route name - block is None
        location.journey.data['MonitoredVehicleJourney']['BlockRef'] = '42'
        del location.journey.block
        self.assertIsNone(location.journey.block)

    @time_machine.travel('2021-05-08T13:00+00:00')
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
                    "Latitude": "87.8245926"
                },
                "Bearing": "0.0",
                "VehicleJourneyRef": "2029",
                "VehicleRef": "SCHI-21210"
            },
            "Extensions": {
                "VehicleJourney": {
                    "DriverRef": "135531"
                }
            }
        }
        command.handle_item(item)
        command.save()

        journey = VehicleJourney.objects.get()
        self.assertEqual(item, journey.data)

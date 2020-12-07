import os
from mock import patch
from freezegun import freeze_time
from vcr import use_cassette
from django.test import TestCase
from busstops.models import Region, DataSource, Operator, OperatorCode, StopPoint, Locality, AdminArea
from ...models import VehicleLocation, VehicleJourney
from ...workers import SiriConsumer
from ..commands import import_bod_avl

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

    @freeze_time('2020-05-01')
    def test_get_items(self):
        command = import_bod_avl.Command()
        command.source = self.source

        with use_cassette(os.path.join(DIR, 'vcr', 'bod_avl.yaml')):
            items = list(command.get_items())

        self.assertEqual(841, len(items))

    def test_update(self):
        command = import_bod_avl.Command()
        with patch('vehicles.management.commands.import_bod_avl.Command.get_items', return_value=[]):
            self.assertEqual(300, command.update())

    # def test_send(self):
    #     def send(_, __):
    #         pass

    #     command = import_bod_avl.Command()
    #     command.send_items(send, [{
    #         "RecordedAtTime": "2020-10-15T07:46:08+00:00",
    #         "MonitoredVehicleJourney": {
    #             "VehicleRef": "DW18_HAM",
    #             "OperatorRef": "HAMSTRA",
    #         }
    #     }])

    #     self.assertEqual(command.identifiers, {'HAMSTRA-DW18_HAM': '2020-10-15T07:46:08+00:00'})

    def test_handle(self):
        consumer = SiriConsumer()

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
                "PublishedLineName": "C",
                "VehicleJourneyRef": "C_20201015_05_53"
            }
        }]

        with self.assertNumQueries(30):
            consumer.sirivm({
                'items': items
            })

        location = VehicleLocation.objects.all()[1]
        self.assertEqual(location.journey.route_name, '843X')
        self.assertEqual(location.journey.destination, 'Soho Road')
        self.assertEqual(location.journey.vehicle.reg, 'SN56AFE')

        location = VehicleLocation.objects.all()[2]
        self.assertEqual(location.journey.vehicle.operator_id, 'HAMS')
        self.assertEqual(location.journey.vehicle.reg, 'DW18HAM')

        self.assertEqual(
            consumer.command.service_cache,
            {'WHIP:WHIP:U:0500CCITY544': None, 'TGTC:TGTC:843X:43000280301': None, 'HAMS:HAMS:C:2400103099': None}
        )

    def test_handle_item(self):
        command = import_bod_avl.Command()
        command.source = self.source

        command.handle_item({
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

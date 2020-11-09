import os
from freezegun import freeze_time
from vcr import use_cassette
from django.test import TestCase
from busstops.models import Region, DataSource, Operator
from ...models import VehicleLocation, VehicleJourney, Vehicle
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

    @freeze_time('2020-05-01')
    def test_get_items(self):
        command = import_bod_avl.Command()
        command.source = self.source

        with use_cassette(os.path.join(DIR, 'vcr', 'bod_avl.yaml')):
            items = list(command.get_items())

        self.assertEqual(841, len(items))

    def test_handle(self):
        command = import_bod_avl.Command()
        command.source = self.source

        command.handle_item({
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
        }, None)

        self.assertEqual(1, VehicleJourney.objects.count())
        self.assertEqual(1, VehicleLocation.objects.count())
        self.assertEqual(1, Vehicle.objects.count())

        item = {
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
        }
        with self.assertNumQueries(10):
            command.handle_item(item, None)
        location = VehicleLocation.objects.last()
        self.assertEqual(location.journey.route_name, '843X')
        self.assertEqual(location.journey.destination, 'Soho Road')
        self.assertEqual(location.journey.vehicle.reg, 'SN56AFE')

        item = {
            "ItemIdentifier": "87043019-595c-4269-b4de-a359ae17a474",
            "RecordedAtTime": "2020-10-15T07:46:08+00:00",
            "ValidUntilTime": "2020-10-15T18:02:11.033673",
            "MonitoredVehicleJourney": {
                "LineRef": "C",
                "BlockRef": "503",
                "VehicleRef": "DW18_HAM",
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
        }
        with self.assertNumQueries(10):
            command.handle_item(item, None)
        location = VehicleLocation.objects.last()
        self.assertEqual(location.journey.vehicle.operator_id, 'HAMS')
        self.assertEqual(location.journey.vehicle.reg, 'DW18HAM')

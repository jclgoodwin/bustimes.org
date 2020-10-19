import os
from mock import patch
from freezegun import freeze_time
from vcr import use_cassette
from django.conf import settings
from django.test import TestCase
from busstops.models import Region, DataSource, Operator
from ...models import VehicleLocation, VehicleJourney, Vehicle
from ..commands import import_bod_avl


class BusOpenDataVehicleLocationsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        region = Region.objects.create(id='EA')
        Operator.objects.bulk_create([
            Operator(id='ARHE', region=region),
            Operator(id='ASES', region=region),
            Operator(id='CBBH', region=region),
            Operator(id='GPLM', region=region),
            Operator(id='KCTB', region=region),
            Operator(id='WHIP', region=region),
            Operator(id='UNOE', region=region),
        ])
        cls.source = DataSource.objects.create(
            name='Bus Open Data',
            url='https://data.bus-data.dft.gov.uk/avl/download/bulk_archive'
        )

    @freeze_time('2020-05-01')
    def test_get_items(self):
        command = import_bod_avl.Command()
        command.source = self.source

        with use_cassette(os.path.join(settings.DATA_DIR, 'vcr', 'bod_avl.yaml')):
            with patch('builtins.print') as mocked_print:
                items = list(command.get_items())
        mocked_print.assert_called_with({})

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

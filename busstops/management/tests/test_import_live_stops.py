import vcr
from django.test import TestCase
from ...models import StopPoint, LiveSource
from ..commands import import_live_stops, import_tfl_stops


class ImportLiveStopsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cardiff_stop = StopPoint.objects.create(
            pk='5710WDB48471',
            common_name='Wood Street',
            locality_centre=False,
            active=True
        )
        cls.command = import_live_stops.Command()
        cls.cardiff = LiveSource.objects.create(name='card')
        cls.london_stop = StopPoint.objects.create(
            pk='490014721F',
            common_name='Wrong Road',
            locality_centre=False,
            active=True
        )

    def test_import_acisconnect(self):
        self.assertEqual(0, len(self.cardiff_stop.live_sources.all()))
        with vcr.use_cassette('data/vcr/cardiff.yaml'):
            self.command.maybe_add_acisconnect_source(self.cardiff_stop, self.cardiff, 'cardiff')
        self.assertEqual(StopPoint.objects.get(pk=self.cardiff_stop.pk).live_sources.all()[0], self.cardiff)

        with vcr.use_cassette('data/vcr/cardiff_clustered_stops.yaml'):
            clustered_stops = self.command.get_clustered_stops('cardiff')
        self.assertIsInstance(clustered_stops, list)
        self.assertEqual(clustered_stops[0], {
            'StopName': 'Keepers Lodge Bridg',
            'ExtensionData': {},
            'StopId': 2017,
            'StopSequenceIndex': 0,
            'ClusterId': 345,
            'Longitude': -3.55504,
            'ClusterCount': 1,
            'StopRef': '5720AWA12434',
            'IsTimingPoint': False,
            'AltStopName': '',
            'Latitude': 51.49254,
            'PublicAccessCode': 'vglgpjd',
            'StopNameLong': 'Waterton',
            'Type': 0,
            'AltStopNameLong': ''
        })
        self.assertEqual(clustered_stops[445], {
            'StopName': None,
            'ExtensionData': {},
            'StopId': 0,
            'StopSequenceIndex': 0,
            'ClusterId': 790,
            'Longitude': -3.15435,
            'ClusterCount': 4,
            'StopRef': None,
            'IsTimingPoint': False,
            'AltStopName': None,
            'Latitude': 51.47945,
            'PublicAccessCode': None,
            'StopNameLong': None,
            'Type': 1,
            'AltStopNameLong': None
        })

        with vcr.use_cassette('data/vcr/cardiff_cluster.yaml'):
            cluster = self.command.get_stops_for_cluster('cardiff', 791)
        self.assertEqual(len(cluster), 6)
        self.assertEqual(cluster[0], {
            'StopName': 'Coed-Y-Gores (W1)',
            'ExtensionData': {},
            'StopId': 7814,
            'StopSequenceIndex': 0,
            'ClusterId': 0,
            'Longitude': -3.15159,
            'ClusterCount': 1,
            'StopRef':
            '5710AWA10324',
            'IsTimingPoint': False,
            'AltStopName': '',
            'Latitude': 51.51761,
            'PublicAccessCode': 'cdijgpw',
            'StopNameLong': 'Coed-Y-Gores',
            'Type': 0,
            'AltStopNameLong': ''
        })

    def test_tfl(self):
        tfl_command = import_tfl_stops.Command()

        self.assertIsNone(tfl_command.handle_row({'Naptan_Atco': 'NONE'}))
        self.assertIsNone(tfl_command.handle_row({'Naptan_Atco': '87'}))
        self.assertIsNone(tfl_command.handle_row({'Naptan_Atco': '7'}))

        with vcr.use_cassette('data/vcr/tfl.yaml'):
            tfl_command.handle_row({
                'Naptan_Atco': '490014721F',
                'Heading': 42
            })

        london_stop = StopPoint.objects.get(atco_code='490014721F')
        self.assertEqual(42, london_stop.get_heading())
        self.assertEqual('Wilmot Street', london_stop.common_name)

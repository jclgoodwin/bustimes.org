import warnings
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
        cls.kent_stop = StopPoint.objects.create(
            pk='2400A020330A',
            naptan_code='2400A020330A',
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
        import_live_stops.DELAY = 0

    def test_import_acislive(self):
        with vcr.use_cassette('data/vcr/acislive_error.yaml'):
            self.command.maybe_add_acislive_source(self.cardiff_stop,
                                                   self.cardiff, 'kent')
        self.cardiff_stop.refresh_from_db()
        self.assertFalse(self.cardiff_stop.live_sources.all())

        with vcr.use_cassette('data/vcr/acislive_kent.yaml'):
            self.command.maybe_add_acislive_source(self.kent_stop,
                                                   self.cardiff, 'kent')
        self.kent_stop.refresh_from_db()
        self.assertEqual(self.cardiff, self.kent_stop.live_sources.all()[0])

    def test_import_acisconnect(self):
        self.assertFalse(self.cardiff_stop.live_sources.all())
        with vcr.use_cassette('data/vcr/cardiff.yaml'):
            self.command.maybe_add_acisconnect_source(self.cardiff_stop,
                                                      self.cardiff, 'cardiff')
        self.cardiff_stop.refresh_from_db()
        self.assertEqual(self.cardiff_stop.live_sources.all()[0], self.cardiff)

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
        LiveSource.objects.create(name='TfL')
        tfl_command = import_tfl_stops.Command()

        with warnings.catch_warnings(record=True) as caught_warnings:
            self.assertIsNone(tfl_command.handle_row({'Naptan_Atco': 'NONE'}))
            self.assertIsNone(tfl_command.handle_row({'Naptan_Atco': '87'}))
            self.assertIsNone(tfl_command.handle_row({'Naptan_Atco': '7'}))
            self.assertEqual(
                str(caught_warnings[0].message),
                "StopPoint matching query does not exist. {'Naptan_Atco': '87'}"
            )
            self.assertTrue('get() returned more than one StopPoint' in str(caught_warnings[1].message))

        with vcr.use_cassette('data/vcr/tfl.yaml'):
            tfl_command.handle_row({
                'Naptan_Atco': '490014721F',
                'Heading': 42
            })

        self.london_stop.refresh_from_db()
        self.assertEqual(42, self.london_stop.get_heading())
        self.assertEqual('Wilmot Street', self.london_stop.common_name)

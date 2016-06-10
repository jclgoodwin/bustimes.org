import vcr
import live
import datetime
from django.test import TestCase
from busstops.models import LiveSource, StopPoint, Service


class LiveDeparturesTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.london_stop = StopPoint.objects.create(
            pk='490014721F',
            common_name='Wilmot Street',
            locality_centre=False,
            active=True,
            admin_area_id=1,
            locality_id=1,
        )
        cls.london_stop.live_sources.add('TfL')

        cls.cardiff = LiveSource.objects.create(pk='card')
        cls.cardiff_stop = StopPoint.objects.create(
            pk='5710WDB48471',
            common_name='Wood Street',
            locality_centre=False,
            active=True,
            admin_area_id=1,
            locality_id=1
        )
        cls.cardiff_stop.live_sources.add('card')

        cls.yorkshire = LiveSource.objects.create(pk='Y')
        cls.yorkshire_stop = StopPoint.objects.create(
            pk='3290YYA00215',
            naptan_code='32900215',
            common_name='Victoria Bar',
            locality_centre=False,
            active=True,
            admin_area_id=1,
            locality_id=1
        )
        cls.yorkshire_stop.live_sources.add('Y')

    def test_tfl(self):
        stop = self.london_stop
        with vcr.use_cassette('data/vcr/tfl.yaml'):
            departures = live.TflDepartures(stop, Service.objects.all()).get_departures()
        row = departures.next()
        self.assertEqual('Stratford City', row['destination'])
        self.assertEqual('388', row['service'])
        self.assertEqual(2016, row['time'].date().year)
        self.assertEqual(6, row['time'].date().month)
        self.assertEqual(5, row['time'].date().day)

        departures = live.get_departures(stop, ())[0]
        self.assertEqual(departures['source'], {
            'url': 'https://tfl.gov.uk/bus/stop/490014721F/wilmot-street',
            'name': 'Transport for London'
        })

    def test_acisconnect_cardiff(self):
        stop = self.cardiff_stop
        with vcr.use_cassette('data/vcr/cardiff.yaml'):
            departures = live.AcisConnectDepartures('cardiff', stop, Service.objects.all()).get_departures()

        self.assertEqual(departures.next(), {
            'destination': 'Churchill Way HL',
            'service': '9',
            'time': '15 mins'
        })

        self.assertEqual(departures.next(), {
            'destination': 'Churchill Way HL',
            'service': '9',
            'time': '45 mins'
        })

        row = departures.next()
        self.assertEqual('Pengam Green Tesco', row['destination'])
        self.assertEqual('11', row['service'])

        self.assertEqual(departures.next(), {
            'destination': 'Customhouse Str JL',
            'service': '95',
            'time': '49 mins'
        })

        departures = live.get_departures(self.cardiff_stop, ())[0]
        self.assertEqual(departures['source'], {
            'url': 'http://cardiff.acisconnect.com/Text/WebDisplay.aspx?stopRef=5710WDB48471',
            'name': 'vixConnect'
        })

    def _test_acis_yorkshire(self, departures):
        self.assertEqual(departures.next(), {
            'destination': 'York Sport Village',
            'service': '66',
            'time': '1 min',
        })
        self.assertEqual(departures.next(), {
            'destination': 'Heslington East Int',
            'service': '44',
            'time': '9 mins',
        })
        self.assertEqual(departures.next(), {
            'destination': 'York Sport Village',
            'service': '66',
            'time': '18:42',
        })
        self.assertEqual(departures.next(), {
            'destination': 'Heslington East Int',
            'service': '44',
            'time': '18:53',
        })

        departures = live.get_departures(self.yorkshire_stop, ())[0]
        self.assertEqual(departures['source'], {
            'url': 'http://yorkshire.acisconnect.com/Text/WebDisplay.aspx?stopRef=32900215',
            'name': 'Your Next Bus'
        })

    def test_acis_yorkshire(self):
        with vcr.use_cassette('data/vcr/acisconnect_yorkshire.yaml'):
            departures = live.AcisConnectDepartures('yorkshire', self.yorkshire_stop, Service.objects.all()).get_departures()
        self._test_acis_yorkshire(departures)

        with vcr.use_cassette('data/vcr/acislive_yorkshire.yaml'):
            departures = live.AcisLiveDepartures('tsy', self.yorkshire_stop, Service.objects.all()).get_departures()
        self._test_acis_yorkshire(departures)

    def test_transporapi_row(self):
        row = live.TransportApiDepartures(self.yorkshire_stop, Service.objects.all()).get_row({
            'direction': 'Bus Station (Norwich City Centre)',
            'source': 'Traveline timetable (nextbuses disabled)',
            'line_name': 'X44',
            'aimed_departure_time': '12:05',
            'date': '2016-06-06',
            'best_departure_estimate': '12:05',
            'mode': 'bus',
            'operator': 'SNDR',
            'line': 'X44',
            'dir': 'outbound'
        })
        self.assertEqual(row, {
            'destination': 'Norwich City Centre',
            'service': 'X44',
            'time': datetime.datetime(2016, 6, 6, 12, 5)
        })

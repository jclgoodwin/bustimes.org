"""Tests for live departures
"""
import datetime
import vcr
from django.test import TestCase
from django.shortcuts import render
from freezegun import freeze_time
from busstops.models import LiveSource, StopPoint, Service
from . import live


class DummyResponse(object):
    def __init__(self, data):
        self.data = data

    def json(self):
        return self.data


class LiveDeparturesTest(TestCase):
    """Tests for live departures
    """
    @classmethod
    def setUpTestData(cls):
        cls.london_stop = StopPoint.objects.create(
            pk='490014721F',
            common_name='Wilmot Street',
            locality_centre=False,
            active=True
        )
        LiveSource.objects.create(name='TfL')
        cls.london_stop.live_sources.add('TfL')

        cls.cardiff = LiveSource.objects.create(pk='card')
        cls.cardiff_stop = StopPoint.objects.create(
            pk='5710WDB48471',
            common_name='Wood Street',
            locality_centre=False,
            active=True
        )
        cls.cardiff_stop.live_sources.add('card')

        cls.yorkshire = LiveSource.objects.create(pk='Y')
        cls.yorkshire_stop = StopPoint.objects.create(
            pk='3290YYA00215',
            naptan_code='32900215',
            common_name='Victoria Bar',
            locality_centre=False,
            active=True
        )
        cls.yorkshire_stop.live_sources.add('Y')

    def test_abstract(self):
        departures = live.Departures(None, ())
        self.assertRaises(NotImplementedError, departures.get_request_url)
        self.assertRaises(NotImplementedError, departures.departures_from_response, None)

    def test_tfl(self):
        """Test the Transport for London live departures source
        """
        with vcr.use_cassette('data/vcr/tfl_arrivals.yaml'):
            row = live.TflDepartures(
                self.london_stop,
                Service.objects.all()
            ).get_departures()[0]
        self.assertEqual('Stratford City', row['destination'])
        self.assertEqual('388', row['service'])
        self.assertEqual(2016, row['time'].date().year)
        self.assertEqual(7, row['time'].date().month)
        self.assertEqual(26, row['time'].date().day)

        departures = live.get_departures(self.london_stop, ())[0]
        self.assertEqual(departures['source'], {
            'url': 'https://tfl.gov.uk/bus/stop/490014721F/wilmot-street',
            'name': 'Transport for London'
        })

        with vcr.use_cassette('data/vcr/tfl_arrivals.yaml'):
            response = self.client.get('/stops/' + self.london_stop.pk)
        # self.assertEqual(response['cache-control'], 'max-age=60')
        self.assertContains(response, """
            <div class="aside box">
                <h2>Next departures</h2>
                <table><tbody>
                    <tr><td>388</td><td>Stratford City</td><td>18:44</td></tr>
                    <tr><td>388</td><td>Stratford City</td><td>18:26</td></tr>
                    <tr><td>8</td><td>Bow Church</td><td>18:26</td></tr>
                    <tr><td>8</td><td>Bow Church</td><td>18:44</td></tr>
                    <tr><td>8</td><td>Bow Church</td><td>18:49</td></tr>
                    <tr><td>8</td><td>Bow Church</td><td>18:33</td></tr>
                    <tr><td>8</td><td>Bow Church</td><td>18:37</td></tr>
                    <tr><td>8</td><td>Bow Church</td><td>18:22</td></tr>
                    <tr><td>D3</td><td>Bethnal Green, Chest Hospital</td><td>18:44</td></tr>
                    <tr><td>D3</td><td>Bethnal Green, Chest Hospital</td><td>18:33</td></tr>
                    <tr><td>D3</td><td>Bethnal Green, Chest Hospital</td><td>18:23</td></tr>
                </tbody></table>
                <p class="credit">Data from
                <a href=https://tfl.gov.uk/bus/stop/490014721F/wilmot-street>
                Transport for London</a></p>
            </div>
        """, html=True)

    @freeze_time('12 Mar 2017 12:00')
    def test_acisconnect_cardiff(self):
        """Test the Cardiff live departures source
        """
        with vcr.use_cassette('data/vcr/cardiff.yaml'):
            departures = live.AcisConnectDepartures(
                'cardiff', self.cardiff_stop, Service.objects.all(), datetime.datetime.now()
            ).get_departures()

        self.assertEqual(departures[0], {
            'destination': 'Churchill Way HL',
            'service': '9',
            'time': None,
            'live': datetime.datetime(2017, 3, 12, 12, 15)
        })

        self.assertEqual(departures[1], {
            'destination': 'Churchill Way HL',
            'service': '9',
            'time': None,
            'live': datetime.datetime(2017, 3, 12, 12, 45)
        })

        self.assertEqual('Pengam Green Tesco', departures[2]['destination'])
        self.assertEqual('11', departures[2]['service'])

        self.assertEqual(departures[3], {
            'destination': 'Customhouse Str JL',
            'service': '95',
            'time': None,
            'live': datetime.datetime(2017, 3, 12, 12, 49)
        })

        with vcr.use_cassette('data/vcr/cardiff.yaml'):
            departures = live.get_departures(self.cardiff_stop, ())[0]
        self.assertTrue('live' in departures['departures'][0])
        self.assertTrue('time' in departures['departures'][0])
        self.assertIsNone(departures['departures'][2]['live'])
        self.assertTrue('time' in departures['departures'][2])
        self.assertEqual(departures['source'], {
            'url': 'http://cardiff.acisconnect.com/Text/WebDisplay.aspx?stopRef=5710WDB48471',
            'name': 'vixConnect'
        })

    def _test_acis_yorkshire(self, departures):
        """Test one of the Yorkshire live departures sources against the same set of data
        """
        print(departures)
        self.assertEqual(departures[:4], [{
            'destination': 'York Sport Village',
            'service': '66',
            'time': None,
            'live': datetime.datetime(2017, 3, 12, 12, 1)
        }, {
            'destination': 'Heslington East Int',
            'service': '44',
            'time': None,
            'live': datetime.datetime(2017, 3, 12, 12, 9)
        }, {
            'destination': 'York Sport Village',
            'service': '66',
            'time': '18:42',
            'live': None
        }, {
            'destination': 'Heslington East Int',
            'service': '44',
            'time': '18:53',
            'live': None
        }])

    @freeze_time('12 Mar 2017 12:00')
    def test_acis_yorkshire(self):
        """Test the two possible (old, new) Yorkshire live departure sources against the same data
        """
        now = datetime.datetime.now()

        with vcr.use_cassette('data/vcr/acisconnect_yorkshire.yaml'):
            departures = live.AcisConnectDepartures(
                'yorkshire',
                self.yorkshire_stop,
                Service.objects.all(),
                now
            ).get_departures()
        self._test_acis_yorkshire(departures)

        with vcr.use_cassette('data/vcr/acislive_yorkshire.yaml'):
            departures = live.AcisLiveDepartures(
                'tsy',
                self.yorkshire_stop,
                Service.objects.all(),
                now
            ).get_departures()
        self._test_acis_yorkshire(departures)

        departures = live.get_departures(self.yorkshire_stop, ())[0]
        self.assertEqual(departures['source'], {
            'url': 'http://yorkshire.acisconnect.com/Text/WebDisplay.aspx?stopRef=32900215',
            'name': 'Your Next Bus'
        })

    # def test_stagecoach(self):
    #     stop = StopPoint(atco_code='64803000')
    #     with vcr.use_cassette('data/vcr/stagecoach.yaml'):
    #         departures = live.StagecoachDepartures(
    #             stop, (), datetime.datetime.now()
    #         ).get_departures()
    #     self.assertEqual(len(departures), 1)
    #     self.assertEqual(departures[0]['destination'], 'Perth')
    #     self.assertEqual(departures[0]['service'], '36')
    #     self.assertEqual(departures[0]['time'].year, 2016)
    #     self.assertEqual(departures[0]['time'].month, 11)
    #     self.assertEqual(departures[0]['time'].day, 13)
    #     self.assertEqual(departures[0]['time'].hour, 18)
    #     self.assertEqual(departures[0]['time'].minute, 52)
    #     self.assertEqual(departures[0]['time'].second, 28)

    def test_transportapi(self):
        """Test the get_row and other methods for Transport API departures
        """
        departures = live.TransportApiDepartures(self.yorkshire_stop, (),
                                                 datetime.date(2016, 6, 10))
        rows = departures.departures_from_response(DummyResponse({'departures': {'all': [{
            'direction': 'Gunton,Weston Road,',
            'expected_departure_time': None,
            'line_name': '101',
            'aimed_departure_time': None,
            'source': 'VIX',
            'best_departure_estimate': None,
            'mode': 'bus',
            'operator': 'FECS',
            'line': '101'
        }, {
            'direction': 'Hellesdon, Bush Roa',
            'expected_departure_time': '22:15',
            'line_name': '37',
            'aimed_departure_time': '22:17',
            'source': 'VIX',
            'best_departure_estimate': '22:15',
            'mode': 'bus',
            'operator': 'FECS',
            'line': '37'
        }, {
            'direction': 'Railway Approach (Sheringham)',
            'source': 'Traveline timetable (nextbuses disabled)',
            'line_name': '44A',
            'aimed_departure_time': '22:47',
            'date': '2016-06-10',
            'best_departure_estimate': '22:47',
            'mode': 'bus',
            'operator': 'SNDR',
            'line': '44A',
            'dir': 'inbound'
        }]}}))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], {
            'destination': 'Hellesdon',
            'service': '37',
            'time': datetime.datetime(2016, 6, 10, 22, 15)
        })
        self.assertEqual(rows[1], {
            'destination': 'Sheringham',
            'service': '44A',
            'time': datetime.datetime(2016, 6, 10, 22, 47)
        })

        east_scotland_row = departures.get_row({
            'mode': 'bus',
            'line': 'N55',
            'line_name': 'N55',
            'direction': 'Edinburgh',
            'operator': 'Stagecoach',
            'aimed_departure_time': None,
            'expected_departure_time': '27:02',
            'best_departure_estimate': '27:02',
            'source': 'Scotland East'
        })
        self.assertEqual(east_scotland_row['destination'], 'Edinburgh')
        self.assertEqual(east_scotland_row['time'].time(), datetime.time(3, 2))

        east_scotland_row_date = departures.get_row({
            'mode': 'bus',
            'line': '38',
            'line_name': '38',
            'direction': 'Stirling',
            'operator': 'First',
            'date': '2016-10-07',
            'expected_departure_date': '2016-10-07',
            'aimed_departure_time': '24:32',
            'expected_departure_time': '24:32',
            'best_departure_estimate': '24:32',
            'source': 'Scotland East'
        })
        self.assertEqual(east_scotland_row_date['destination'], 'Stirling')
        self.assertEqual(east_scotland_row_date['time'].time(),
                         datetime.time(0, 32))

        self.assertEqual(
            departures.get_request_url(),
            'http://transportapi.com/v3/uk/bus/stop/3290YYA00215/live.json'
        )
        self.assertEqual(departures.get_request_params(), {
            'app_id': None,
            'app_key': None,
            'nextbuses': 'no',
            'group': 'no',
        })

    def test_max_age(self):
        """Test the get_max_age() method
        """
        # Empty departures list should be cached until midnight
        self.assertEqual(live.get_max_age((), datetime.datetime(2016, 6, 10, 22, 47)), 4380)

        # Error should be cached for 3600 seconds
        self.assertEqual(live.get_max_age(None, 'chutney'), 3600)

        # If the first departure is in the past, cache for 60 seconds
        self.assertEqual(live.get_max_age(({
            'destination': 'Sheringham',
            'service': '44A',
            'time': datetime.datetime(2016, 6, 10, 22, 47)
        },), datetime.datetime(2016, 6, 10, 22, 59)), 60)

        # If the first departure is 43030 seconds in the future, cache for 43030 seconds
        self.assertEqual(live.get_max_age(({
            'destination': 'Sheringham',
            'service': '44A',
            'time': datetime.datetime(2016, 6, 10, 22, 47)
        },), datetime.datetime(2016, 6, 10, 10, 50, 50)), 43030)

    def test_render(self):
        response = render(None, 'departures.html', {
            'departures': [
                {
                    'time': datetime.datetime(1994, 5, 4, 11, 53),
                    'service': 'X98',
                    'destination': 'Bratislava'
                },
                {
                    'time': datetime.datetime(1994, 5, 7, 11, 53),
                    'service': '9',
                    'destination': 'Shilbottle'
                }
            ]
        })
        self.assertContains(response, """
            <div class="aside box">
                <h2>Next departures</h2>
                <table><tbody>
                    <tr><td>X98</td><td>Bratislava</td><td>11:53</td></tr>
                </tbody></table>
                <h3>Saturday</h3>
                <table><tbody>
                    <tr><td>9</td><td>Shilbottle</td><td>11:53</td></tr>
                </tbody></table>
                <p class="credit"></p>
            </div>
        """, html=True)

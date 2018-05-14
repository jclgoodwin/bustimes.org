# coding=utf-8
"""Tests for live departures
"""
import vcr
from datetime import date, time, datetime
from django.test import TestCase
from django.shortcuts import render
from freezegun import freeze_time
from busstops.models import LiveSource, StopPoint, Service, Region, Operator, StopUsage, Journey, StopUsageUsage
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

        cls.region = Region.objects.create(id='W', name='Wales')
        cls.stagecoach_stop = StopPoint.objects.create(atco_code='64801092', active=True,
                                                       locality_centre=False)
        stagecoach_operator = Operator.objects.create(id='SCOX',
                                                      name='Stagecoach Oxenholme',
                                                      region_id='W')
        cls.stagecoach_service = Service.objects.create(service_code='15', line_name='15',
                                                        region_id='W', date='2017-01-01')
        cls.stagecoach_service.operator.add(stagecoach_operator)
        StopUsage.objects.create(stop=cls.stagecoach_stop, service=cls.stagecoach_service, order=1)

        translink_metro_operator = Operator.objects.create(id='MET', name='Translink Metro', region_id='W')
        cls.translink_metro_stop = StopPoint.objects.create(atco_code='700000001415', active=True,
                                                            locality_centre=False)
        translink_metro_service = Service.objects.create(service_code='2D_MET', line_name='2D', region_id='W',
                                                         date='2017-01-01')
        translink_metro_service.operator.add(translink_metro_operator)
        StopUsage.objects.create(stop=cls.translink_metro_stop, service=translink_metro_service, order=0)

        stagecoach_journey = Journey.objects.create(datetime='2017-03-14T20:23:00Z', service=cls.stagecoach_service,
                                                    destination=cls.cardiff_stop)
        StopUsageUsage.objects.bulk_create([
            StopUsageUsage(journey=stagecoach_journey, order=0, datetime=datetime, stop=cls.stagecoach_stop)
            for datetime in ['2017-03-14T20:23:00Z', '2017-03-14T21:23:00Z', '2017-03-28 18:53:00+01:00']
        ])

        cls.norfolk_stop = StopPoint.objects.create(atco_code='2900M115', active=True, locality_centre=False)
        Service.objects.create(service_code='9', line_name='9', region_id='W', date='2018-01-04')
        norfolk_journey = Journey.objects.create(datetime='2018-01-04T10:00:00+00:00', service_id='9',
                                                 destination=cls.yorkshire_stop)
        StopUsageUsage.objects.create(journey=norfolk_journey, order=0, datetime='2018-01-04T10:02:00+00:00',
                                      stop=cls.norfolk_stop)

        cls.singapore_stop = StopPoint.objects.create(atco_code='sg-53341', active=True, locality_centre=False)
        StopPoint.objects.create(atco_code='sg-55509', common_name='Yio Chu Kang Interchange', active=True,
                                 locality_centre=False)

        cls.jersey_stop = StopPoint.objects.create(atco_code='je-2734', active=True, locality_centre=False)

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
                ()
            ).get_departures()[0]
        self.assertEqual('Bow Church', row['destination'])
        self.assertEqual('8', row['service'])
        self.assertEqual(2016, row['live'].date().year)
        self.assertEqual(7, row['live'].date().month)
        self.assertEqual(26, row['live'].date().day)

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
                    <tr><td>8</td><td>Bow Church</td><td>18:22⚡</td></tr>
                    <tr><td>D3</td><td>Bethnal Green, Chest Hospital</td><td>18:23⚡</td></tr>
                    <tr><td>8</td><td>Bow Church</td><td>18:26⚡</td></tr>
                    <tr><td>388</td><td>Stratford City</td><td>18:26⚡</td></tr>
                    <tr><td>8</td><td>Bow Church</td><td>18:33⚡</td></tr>
                    <tr><td>D3</td><td>Bethnal Green, Chest Hospital</td><td>18:33⚡</td></tr>
                    <tr><td>8</td><td>Bow Church</td><td>18:37⚡</td></tr>
                    <tr><td>388</td><td>Stratford City</td><td>18:44⚡</td></tr>
                    <tr><td>D3</td><td>Bethnal Green, Chest Hospital</td><td>18:44⚡</td></tr>
                    <tr><td>8</td><td>Bow Church</td><td>18:44⚡</td></tr>
                    <tr><td>8</td><td>Bow Church</td><td>18:49⚡</td></tr>
                </tbody></table>
                <p class="credit">⚡ denotes real-time times</p>
                <p class="credit">
                    <a href="https://tfl.gov.uk/bus/stop/490014721F/wilmot-street">Transport for London</a>
                </p>
            </div>
        """, html=True)

    @freeze_time('12 Mar 2017 12:00')
    def test_acisconnect_cardiff(self):
        """Test the Cardiff live departures source
        """
        with vcr.use_cassette('data/vcr/cardiff.yaml'):
            departures = live.AcisConnectDepartures(
                'cardiff', self.cardiff_stop, (), datetime.now()
            ).get_departures()

        self.assertEqual(departures[0], {
            'destination': 'Churchill Way HL',
            'service': '9',
            'time': None,
            'live': datetime(2017, 3, 12, 12, 15)
        })

        self.assertEqual(departures[1], {
            'destination': 'Churchill Way HL',
            'service': '9',
            'time': None,
            'live': datetime(2017, 3, 12, 12, 45)
        })

        self.assertEqual('Pengam Green Tesco', departures[2]['destination'])
        self.assertEqual('11', departures[2]['service'])

        self.assertEqual(departures[3], {
            'destination': 'Customhouse Str JL',
            'service': '95',
            'time': None,
            'live': datetime(2017, 3, 12, 12, 49)
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
        self.assertEqual(departures[:4], [{
            'destination': 'York Sport Village',
            'service': '66',
            'time': None,
            'live': datetime(2017, 3, 12, 12, 1)
        }, {
            'destination': 'Heslington East Int',
            'service': '44',
            'time': None,
            'live': datetime(2017, 3, 12, 12, 9)
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
        now = datetime.now()

        with vcr.use_cassette('data/vcr/acisconnect_yorkshire.yaml'):
            departures = live.AcisConnectDepartures(
                'yorkshire',
                self.yorkshire_stop,
                (),
                now
            ).get_departures()
        self._test_acis_yorkshire(departures)

        with vcr.use_cassette('data/vcr/acislive_yorkshire.yaml'):
            departures = live.AcisLiveDepartures(
                'tsy',
                self.yorkshire_stop,
                (),
                now
            ).get_departures()
        self._test_acis_yorkshire(departures)

        departures = live.get_departures(self.yorkshire_stop, ())[0]
        self.assertEqual(departures['source'], {
            'url': 'http://yorkshire.acisconnect.com/Text/WebDisplay.aspx?stopRef=32900215',
            'name': 'Your Next Bus'
        })

    def test_dublin(self):
        stop = StopPoint(atco_code='8220DB07602')
        with vcr.use_cassette('data/vcr/dublin.yaml'):
            departures, max_age = live.get_departures(stop, ())
        self.assertEqual(max_age, 60)
        self.assertEqual(len(departures['departures']), 12)
        self.assertEqual(departures['departures'][4], {
            'time': datetime(2017, 6, 5, 12, 43),
            'live': datetime(2017, 6, 5, 12, 35, 58),
            'destination': 'Dublin Airport',
            'service': '16'
        })

    @freeze_time('25 December 1904')
    def test_translink_metro(self):
        with vcr.use_cassette('data/vcr/translink_metro.yaml'):
            res = self.client.get(self.translink_metro_stop.get_absolute_url())
        self.assertEqual(res.context_data['departures'][0]['live'].date(), date(1904, 12, 25))
        self.assertEqual(res.context_data['departures'][1]['live'].date(), date(1904, 12, 25))
        self.assertEqual(res.context_data['departures'][2]['live'].date(), date(1904, 12, 25))
        self.assertEqual(res.context_data['departures'][0]['live'].time(), time(0, 0))

    @freeze_time('14 Mar 2017 20:00')
    def test_stagecoach(self):
        with vcr.use_cassette('data/vcr/stagecoach.yaml'):
            res = self.client.get('/stops/64801092')
        self.assertContains(res, '<td><a href=/services/15>15</a></td>', html=True)
        self.assertContains(res, '<td>Hillend</td>')
        self.assertEqual(res.context_data['departures'][0]['service'], self.stagecoach_service)
        self.assertEqual(res.context_data['departures'][0]['live'].time(), time(20, 37, 51))
        self.assertEqual(res.context_data['departures'][1]['service'], '7')
        self.assertEqual(res.context_data['departures'][1]['live'].time(), time(21, 17, 28))
        self.assertEqual(res.context_data['departures'][2]['service'], self.stagecoach_service)
        self.assertEqual(res.context_data['departures'][2]['live'].time(), time(21, 38, 21))

    @freeze_time('28 Mar 2017 17:00')
    def test_stagecoach_timezone(self):
        with vcr.use_cassette('data/vcr/stagecoach_timezone.yaml'):
            res = self.client.get('/stops/64801092')
        self.assertEqual(res.context_data['departures'][0]['destination'].common_name, 'Wood Street')
        self.assertEqual(res.context_data['departures'][1]['destination'], 'Hillend')
        self.assertEqual(res.context_data['departures'][2]['destination'], 'Perth')
        self.assertEqual(res.context_data['departures'][0]['service'].line_name, '15')
        self.assertEqual(res.context_data['departures'][1]['service'], '7')
        self.assertEqual(res.context_data['departures'][2]['service'].line_name, '15')
        self.assertEqual(str(res.context_data['departures'][0]['time']), '2017-03-28 18:53:00+01:00')
        self.assertEqual(str(res.context_data['departures'][1]['time']), '2017-03-28 19:08:00+01:00')
        self.assertEqual(str(res.context_data['departures'][1]['live']), '2017-03-28 19:08:25+01:00')
        self.assertEqual(str(res.context_data['departures'][2]['time']), '2017-03-28 19:20:00+01:00')
        self.assertEqual(str(res.context_data['departures'][2]['live']), '2017-03-28 19:24:08+01:00')

    def test_transportapi(self):
        """Test the get_row and other methods for Transport API departures
        """
        departures = live.TransportApiDepartures(self.yorkshire_stop, (), date(2016, 6, 10))
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
        }, {
            'direction': 'Railway Approach (Sheringham)',
            'source': 'Traveline timetable (nextbuses disabled)',
            'line_name': '44A',
            'aimed_departure_time': '06:47',
            'date': '2016-06-11',
            'best_departure_estimate': '06:47',
            'mode': 'bus',
            'operator': 'SNDR',
            'line': '44A',
            'dir': 'inbound'
        }]}}))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], {
            'destination': 'Hellesdon',
            'service': '37',
            'time': datetime(2016, 6, 10, 22, 17),
            'live': datetime(2016, 6, 10, 22, 15)
        })
        self.assertEqual(rows[1], {
            'destination': 'Sheringham',
            'service': '44A',
            'time': datetime(2016, 6, 10, 22, 47),
            'live': None
        })

        self.assertEqual(departures._get_time('27:02'), '03:02')
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
        self.assertEqual(east_scotland_row['live'].time(), time(3, 2))

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
        self.assertEqual(east_scotland_row_date['live'].time(), time(0, 32))

        self.assertEqual(
            departures.get_request_url(),
            'http://transportapi.com/v3/uk/bus/stop/3290YYA00215/live.json'
        )
        self.assertEqual(departures.get_request_params(), {
            'app_id': None,
            'app_key': None,
            'group': 'no',
        })

    def test_blend(self):
        a = [{
            'service': 'X98',
            'time': datetime(2017, 4, 21, 20, 10),
            'live': datetime(2017, 4, 21, 20, 2)
        }]
        b = [{
            'service': Service(line_name='X98'),
            'time': datetime(2017, 4, 21, 20, 10),
            'live': datetime(2017, 4, 21, 20, 5)
        }]

        live.blend(a, b)
        self.assertEqual(a, [{
            'service': 'X98',
            'time': datetime(2017, 4, 21, 20, 10),
            'live': datetime(2017, 4, 21, 20, 5)
        }])

        live.blend(b, a)
        self.assertEqual(b, [{
            'service': Service(line_name='X98'),
            'time': datetime(2017, 4, 21, 20, 10),
            'live': datetime(2017, 4, 21, 20, 5)
        }])

    def test_max_age(self):
        """Test the get_max_age() method
        """
        # Empty departures list should be cached until midnight
        self.assertEqual(live.get_max_age((), datetime(2016, 6, 10, 22, 47)), 4380)

        # Error should be cached for 3600 seconds
        self.assertEqual(live.get_max_age(None, 'chutney'), 3600)

        # If the first departure is in the past, cache for 60 seconds
        self.assertEqual(live.get_max_age(({
            'destination': 'Sheringham',
            'service': '44A',
            'time': datetime(2016, 6, 10, 22, 47)
        },), datetime(2016, 6, 10, 22, 59)), 60)

        # If the first departure is 43030 seconds in the future, cache for 43030 seconds
        self.assertEqual(live.get_max_age(({
            'destination': 'Sheringham',
            'service': '44A',
            'time': datetime(2016, 6, 10, 22, 47)
        },), datetime(2016, 6, 10, 10, 50, 50)), 43030)

    def test_render(self):
        response = render(None, 'departures.html', {
            'departures': [
                {
                    'time': datetime(1994, 5, 4, 11, 53),
                    'service': 'X98',
                    'destination': 'Bratislava'
                },
                {
                    'time': datetime(1994, 5, 7, 11, 53),
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
            </div>
        """, html=True)

    def test_lambda(self):
        with vcr.use_cassette('data/vcr/lambda_manchester.yaml'):
            departures = live.LambdaDepartures(StopPoint(atco_code='1800SB04611'), ()).get_departures()
        self.assertEqual(str(departures[0]['time']), '2018-05-14 19:47:00+01:00')

    def test_blended_lambda(self):
        with freeze_time('4 Jan 2018 10:02'):
            with vcr.use_cassette('data/vcr/lambda_norfolk.yaml'):
                response = self.client.get(self.norfolk_stop.get_absolute_url())
        self.assertContains(
            response, '<tr><td><a href=/services/9>9</a></td><td>Victoria Bar</td><td>10:03⚡</td></tr>',
            html=True
        )
        self.assertEqual(str(response.context_data['departures'][0]['live']), '2018-01-04 10:03:21+00:00')

        with freeze_time('4 Jan 2018 10:02:01'):
            with vcr.use_cassette('data/vcr/lambda_norfolk.yaml'):
                response = self.client.get(self.norfolk_stop.get_absolute_url())
        # Live departures have (unfortunately) not been fetched, because the only departure is (barely) in the past
        self.assertEqual(response.context_data['departures'], [])

    def test_singapore(self):
        with vcr.use_cassette('data/vcr/singapore_live.yaml'):
            response = self.client.get(self.singapore_stop.get_absolute_url())
        self.assertEqual(len(response.context_data['departures']), 9)
        self.assertEqual(response.context_data['departures'][0]['service'], '162M')
        self.assertEqual(str(response.context_data['departures'][0]['destination']), 'Yio Chu Kang Interchange')

    def test_jersey(self):
        with vcr.use_cassette('data/vcr/jersey_live.yaml'):
            response = self.client.get(self.jersey_stop.get_absolute_url())
        self.assertEqual(len(response.context_data['departures']), 9)
        self.assertEqual(response.context_data['departures'][0]['service'], '16')
        self.assertEqual(str(response.context_data['departures'][0]['destination']), 'St Helier')

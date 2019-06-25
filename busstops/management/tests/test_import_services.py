# coding=utf-8
import os
import xml.etree.cElementTree as ET
import zipfile
import warnings
from datetime import date, time
from freezegun import freeze_time
from django.test import TestCase, override_settings
from django.contrib.gis.geos import Point
from django.core.management import call_command
from ...models import (Operator, DataSource, OperatorCode, Service, Region, StopPoint, Journey, StopUsageUsage,
                       ServiceDate)
from ..commands import import_services, generate_departures


FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


def clean_up():
    # clean up
    for filename in ('EA.zip', 'S.zip', 'NCSD.zip', 'NW.zip'):
        path = os.path.join(FIXTURES_DIR, filename)
        if os.path.exists(path):
            os.remove(path)


@override_settings(TNDS_DIR=FIXTURES_DIR)
class ImportServicesTest(TestCase):
    "Tests for parts of the command that imports services from TNDS"

    command = import_services.Command()

    @classmethod
    @freeze_time('2016-01-01')
    def setUpTestData(cls):
        clean_up()

        cls.ea = Region.objects.create(pk='EA', name='East Anglia')
        cls.gb = Region.objects.create(pk='GB', name='Großbritannien')
        cls.sc = Region.objects.create(pk='S', name='Scotland')
        cls.nw = Region.objects.create(pk='NW', name='North West')
        cls.w = Region.objects.create(pk='W', name='Wales')
        cls.london = Region.objects.create(pk='L', name='London')

        cls.fecs = Operator.objects.create(pk='FECS', region_id='EA', name='First in Norfolk & Suffolk')
        cls.megabus = Operator.objects.create(pk='MEGA', region_id='GB', name='Megabus')
        cls.fabd = Operator.objects.create(pk='FABD', region_id='S', name='First Aberdeen')

        nocs = DataSource.objects.create(name='National Operator Codes', datetime='2018-02-01 00:00+00:00')
        east_anglia = DataSource.objects.create(name='EA', datetime='2018-02-01 00:00+00:00')
        OperatorCode.objects.create(operator=cls.fecs, source=east_anglia, code='FECS')
        OperatorCode.objects.create(operator=cls.megabus, source=nocs, code='MEGA')
        OperatorCode.objects.create(operator=cls.fabd, source=nocs, code='FABD')

        for atco_code, common_name, indicator, lat, lng in (
                ('639004572', 'Bulls Head', 'adj', -2.5042125060, 53.7423055225),
                ('639004562', 'Markham Road', 'by"', -2.5083672338, 53.7398252112),
                ('639004554', 'Witton Park', 'opp', -2.5108434749, 53.7389877672),
                ('639004552', 'The Griffin', 'adj', -2.4989239373, 53.7425523688),
                ('049004705400', 'Kingston District Centre', 'o/s', 0, 0),
                ('4200F156472', 'Asda', 'opp', 0, 0),
                ('2900A1820', 'Leys Lane', 'adj', 0, 0),
                ('1000DDDV4248', 'Dinting Value Works', '', 0, 0),
        ):
            StopPoint.objects.create(
                atco_code=atco_code, locality_centre=False, active=True, common_name=common_name,
                indicator=indicator, latlong=Point(lng, lat, srid=4326)
            )

        with override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}):
            # simulate an East Anglia zipfile:
            cls.write_files_to_zipfile_and_import('EA.zip', ['ea_21-13B-B-y08-1.xml'])

            # simulate a Scotland zipfile:
            cls.write_files_to_zipfile_and_import('S.zip', ['SVRABBN017.xml', 'CGAO305.xml'])

            # simulate a North West zipfile:
            cls.write_files_to_zipfile_and_import('NW.zip', ['NW_04_GMN_2_1.xml', 'NW_04_GMN_2_2.xml',
                                                             'NW_04_GMS_237_1.xml', 'NW_04_GMS_237_2.xml'])

        cls.ea_service = Service.objects.get(pk='ea_21-13B-B-y08')
        cls.sc_service = Service.objects.get(pk='ABBN017')

        # simulate a National Coach Service Database zip file
        ncsd_zipfile_path = os.path.join(FIXTURES_DIR, 'NCSD.zip')
        with zipfile.ZipFile(ncsd_zipfile_path, 'a') as ncsd_zipfile:
            for line_name in ('M11A', 'M12'):
                file_name = 'Megabus_Megabus14032016 163144_MEGA_' + line_name + '.xml'
                cls.write_file_to_zipfile(ncsd_zipfile, os.path.join('NCSD_TXC', file_name))
            ncsd_zipfile.writestr(
                'IncludedServices.csv',
                'Operator,LineName,Dir,Description\nMEGA,M11A,O,Belgravia - Liverpool\nMEGA,M12,O,Shudehill - Victoria'
            )
        call_command(cls.command, ncsd_zipfile_path)

        # test re-importing a previously imported service again
        call_command(cls.command, ncsd_zipfile_path)

        with freeze_time('2000-01-01'):
            call_command('generate_departures', 'GB')
        with freeze_time('2016-12-31'):
            call_command('generate_departures', 'GB')
        with freeze_time('2017-01-01'):
            call_command('generate_departures', 'GB')
            call_command('generate_departures', 'GB')

        cls.gb_m11a = Service.objects.get(pk='M11A_MEGA')
        cls.gb_m12 = Service.objects.get(pk='M12_MEGA')

    @classmethod
    def write_files_to_zipfile_and_import(cls, zipfile_name, filenames):
        zipfile_path = os.path.join(FIXTURES_DIR, zipfile_name)
        with zipfile.ZipFile(zipfile_path, 'a') as open_zipfile:
            for filename in filenames:
                cls.write_file_to_zipfile(open_zipfile, filename)
        call_command(cls.command, zipfile_path)

    @staticmethod
    def write_file_to_zipfile(open_zipfile, filename):
        open_zipfile.write(os.path.join(FIXTURES_DIR, filename), filename)

    def test_sanitize_description(self):
        testcases = (
            (
                'Bus Station bay 5,Blyth - Grange Road turning circle,Widdrington Station',
                'Blyth - Widdrington Station'
            ),
            (
                '      Bus Station-Std C,Winlaton - Ryton Comprehensive School,Ryton     ',
                'Winlaton - Ryton'
            ),
        )

        for inp, outp in testcases:
            self.assertEqual(self.command.sanitize_description(inp), outp)

    def test_infer_from_filename(self):
        """
        Given a filename string
        get_net() should return a (net, service_code, line_ver) tuple if appropriate,
        or ('', None, None) otherwise.
        """
        data = (
            ('ea_21-2-_-y08-1.xml', ('ea', 'ea_21-2-_-y08', '1')),
            ('ea_21-27-D-y08-1.xml', ('ea', 'ea_21-27-D-y08', '1')),
            ('tfl_52-FL2-_-y08-1.xml', ('tfl', 'tfl_52-FL2-_-y08', '1')),
            ('suf_56-FRY-1-y08-15.xml', ('suf', 'suf_56-FRY-1-y08', '15')),
            ('NATX_330.xml', ('', None, None)),
            ('NE_130_PB2717_21A.xml', ('', None, None)),
            ('SVRABAN007-20150620-9.xml', ('', None, None)),
            ('SVRWLCO021-20121121-13693.xml', ('', None, None)),
            ('National Express_NX_atco_NATX_T61.xml', ('', None, None)),
            ('SnapshotNewportBus_TXC_2015714-0317_NTAO155.xml', ('', None, None)),
            ('ArrivaCymru51S-Rhyl-StBrigid`s-Denbigh1_TXC_2016108-0319_DGAO051S.xml', ('', None, None)),
        )

        for filename, parts in data:
            self.assertEqual(self.command.infer_from_filename(filename), parts)

    def test_get_operator_name(self):
        blue_triangle_element = ET.fromstring("""
            <txc:Operator xmlns:txc='http://www.transxchange.org.uk/' id='OId_BE'>
                <txc:OperatorCode>BE</txc:OperatorCode>
                <txc:OperatorShortName>BLUE TRIANGLE BUSES LIM</txc:OperatorShortName>
                <txc:OperatorNameOnLicence>BLUE TRIANGLE BUSES LIMITED</txc:OperatorNameOnLicence>
                <txc:TradingName>BLUE TRIANGLE BUSES LIMITED</txc:TradingName>
            </txc:Operator>
        """)
        self.assertEqual(self.command.get_operator_name(blue_triangle_element), 'BLUE TRIANGLE BUSES LIMITED')

    def test_get_operator(self):
        element = ET.fromstring("""
            <txc:Operator xmlns:txc="http://www.transxchange.org.uk/" id="OId_RRS">
                <txc:OperatorCode>RRS</txc:OperatorCode>
                <txc:OperatorShortName>Replacement Service</txc:OperatorShortName>
                <txc:OperatorNameOnLicence>Replacement Service</txc:OperatorNameOnLicence>
                <txc:TradingName>Replacement Service</txc:TradingName>
            </txc:Operator>
        """)
        self.assertIsNone(self.command.get_operator(element))

        with warnings.catch_warnings(record=True) as caught_warnings:
            self.assertIsNone(self.command.get_operator(ET.fromstring("""
                <txc:Operator xmlns:txc="http://www.transxchange.org.uk/" id="OId_RRS">
                    <txc:OperatorCode>BEAN</txc:OperatorCode>
                    <txc:TradingName>Bakers</txc:TradingName>
                </txc:Operator>
            """)))
            self.assertTrue('No operator found for element' in str(caught_warnings[0].message))

    def test_get_line_name_and_brand(self):
        with warnings.catch_warnings(record=True) as caught_warnings:
            element = ET.fromstring("""<txc:Service xmlns:txc="http://www.transxchange.org.uk/"><txc:Lines><txc:Line>
                <txc:LineName>Llanfairpwllgwyngyllgogerychwyrndrobwllllantysiliogogogoch Park &amp; Ride</txc:LineName>
                </txc:Line></txc:Lines></txc:Service>""")
            line_name_and_brand = self.command.get_line_name_and_brand(element, None)
            self.assertEqual(line_name_and_brand,
                             ('Llanfairpwllgwyngyllgogerychwyrndrobwllllantysiliogogogoch Park ', ''))
            self.assertTrue('too long in' in str(caught_warnings[0].message))

            for (line_name, line_brand) in (('ZAP', 'Cityzap'), ('TAD', 'Tadfaster')):
                element[0][0][0].text = line_name
                self.assertEqual(self.command.get_line_name_and_brand(element, None), (line_name, line_brand))

    @classmethod
    def do_service(cls, filename, region_id):
        filename = '%s.xml' % filename
        if region_id == 'GB':
            region_id = 'NCSD'
        cls.command.set_region('%s.zip' % region_id)
        path = os.path.join(FIXTURES_DIR, filename)
        with open(path) as xml_file:
            cls.command.do_service(xml_file, filename)

    def test_do_service_invalid(self):
        """A file with some wrong references should be silently ignored"""
        self.do_service('NW_05_PBT_6_1', 'GB')

    @freeze_time('30 October 2017')
    def test_do_service_with_empty_pattern(self):
        """A file with a JourneyPattern with no JourneyPatternSections should be imported"""
        with warnings.catch_warnings(record=True) as caught_warnings:
            self.do_service('swe_33-9A-A-y10-2', 'GB')
            self.assertEqual(len(caught_warnings), 3)
        self.assertTrue(Service.objects.filter(service_code='swe_33-9A-A-y10').exists())

    @freeze_time('1 October 2017')
    def test_service_nw(self):
        # 2
        service = Service.objects.get(service_code='NW_04_GMN_2_1')
        self.assertEqual(service.description, 'intu Trafford Centre - Eccles - Swinton - Bolton')

        res = self.client.get(service.get_absolute_url())

        self.assertEqual(2, len(res.context_data['timetables']))

        # Outside of one timetable's oprating period, only one timetable should be shown
        with freeze_time('1 September 2017'):
            res = self.client.get(service.get_absolute_url() + '?date=2017-09-01')
        self.assertEqual(1, len(res.context_data['timetables']))

        self.assertEqual(0, service.stopusage_set.all().count())

        # Stagecoach Manhester 237
        service = Service.objects.get(service_code='NW_04_GMS_237_1')
        self.assertEqual(service.description, 'Glossop - Stalybridge - Ashton')

        # On a Sunday, both timetables should be shown
        res = self.client.get(service.get_absolute_url())
        self.assertEqual(2, len(res.context_data['timetables']))

        # On a Tuesday, only one timetable should be shown
        res = self.client.get(service.get_absolute_url() + '?date=2017-10-03')
        self.assertEqual(1, len(res.context_data['timetables']))

        self.assertEqual(1, service.stopusage_set.all().count())

    @freeze_time('30 December 2016')
    @override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
    def test_service_dates(self):
        self.assertEqual(14, ServiceDate.objects.count())

        # speed up
        self.ea_service.current = False
        self.ea_service.save()

        call_command('generate_service_dates')
        self.assertEqual(28, ServiceDate.objects.count())

        call_command('generate_service_dates')
        self.assertEqual(28, ServiceDate.objects.count())

    @freeze_time('3 October 2016')
    def test_do_service_ea(self):
        service = self.ea_service

        self.assertEqual(str(service), '13B - Turquoise Line - Norwich - Wymondham - Attleborough')
        self.assertEqual(service.line_name, '13B')
        self.assertEqual(service.line_brand, 'Turquoise Line')
        self.assertTrue(service.show_timetable)
        self.assertTrue(service.current)
        self.assertEqual(service.outbound_description, 'Norwich - Wymondham - Attleborough')
        self.assertEqual(service.inbound_description, 'Attleborough - Wymondham - Norwich')
        self.assertEqual(service.operator.first(), self.fecs)
        self.assertEqual(
            service.get_traveline_link()[0],
            'http://www.travelinesoutheast.org.uk/se/XSLT_TTB_REQUEST' +
            '?line=2113B&lineVer=1&net=ea&project=y08&sup=B&command=direct&outputFormat=0'
        )

        res = self.client.get(service.get_absolute_url())
        self.assertEqual(res.context_data['breadcrumb'], [self.ea, self.fecs])
        self.assertContains(res, """
            <tr class="OTH">
                <th>Norwich Brunswick Road</th><td>19:48</td><td>22:56</td>
            </tr>
        """, html=True)
        self.assertContains(res, '<option selected value="2016-10-03">Monday 3 October 2016</option>')

        # Test the fallback version without a timetable (just a list of stops)
        service.show_timetable = False
        service.save()
        res = self.client.get(service.get_absolute_url())
        self.assertContains(res, '<span itemprop="name">Leys Lane (adj)</span>')
        self.assertContains(res, 'Norwich - Wymondham - Attleborough')
        self.assertContains(res, 'Attleborough - Wymondham - Norwich')

        # Re-import the service, now that the operating period has passed
        with freeze_time('2016-10-30'):
            call_command(self.command, os.path.join(FIXTURES_DIR, 'EA.zip'))
        service.refresh_from_db()
        self.assertFalse(service.current)

    @freeze_time('22 January 2017')
    def test_do_service_m11a(self):
        res = self.client.get('/services/m11a-belgravia-liverpool?date=ceci n\'est pas une date')

        service = res.context_data['object']

        self.assertEqual(str(service), 'M11A - Belgravia - Liverpool')
        self.assertTrue(service.show_timetable)
        self.assertEqual(service.operator.first(), self.megabus)
        self.assertEqual(
            service.get_traveline_link()[0],
            'http://www.travelinesoutheast.org.uk/se/XSLT_TTB_REQUEST' +
            '?line=11M11&sup=A&net=nrc&project=y08&command=direct&outputFormat=0'
        )

        self.assertEqual(res.context_data['breadcrumb'], [self.gb, self.megabus])
        self.assertTemplateUsed(res, 'busstops/service_detail.html')
        self.assertContains(res, '<h1>M11A - Belgravia - Liverpool</h1>')
        self.assertContains(res, '<option selected value="2017-01-22">Sunday 22 January 2017</option>')
        self.assertContains(
            res,
            """
            <td colspan="7">
            Book at <a
            href="https://www.awin1.com/awclick.php?mid=2678&amp;id=242611&amp;clickref=urlise&amp;p=https%3A%2F%2Fuk.megabus.com"
            rel="nofollow">
            megabus.com</a> or 0900 1600900 (65p/min + network charges)
            </td>
            """,
            html=True
        )

    @override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
    @freeze_time('1 Dec 2016')
    def test_do_service_m12(self):
        res = self.client.get(self.gb_m12.get_absolute_url())

        # The date of the next StopUsageUsage should be used, even though today is 1 Dec 2016
        self.assertContains(res, '<option selected value="2017-01-01">Sunday 1 January 2017</option>')

        groupings = res.context_data['timetables'][0].groupings
        outbound_stops = [str(row.part.stop) for row in groupings[0].rows]
        inbound_stops = [str(row.part.stop) for row in groupings[1].rows]
        self.assertEqual(outbound_stops, [
            'Belgravia Victoria Coach Station', '049004705400', 'Rugby ASDA', 'Fosse Park ASDA',
            'Loughborough Holywell Way', 'Nottingham Broad Marsh Bus Station', 'Meadowhall Interchange',
            'Leeds City Centre York Street', 'Bradford City Centre Hall Ings',
            'Huddersfield Town Centre Market Street', 'Leeds City Centre Bus Stn',
            'Shudehill Interchange', 'Middlesbrough Bus Station Express Lounge', 'Sunderland Interchange',
            'Newcastle upon Tyne John Dobson Street',
        ])
        self.assertEqual(inbound_stops, [
            'Huddersfield Town Centre Market Street', 'Bradford City Centre Interchange',
            'Newcastle upon Tyne John Dobson Street', 'Sunderland Interchange',
            'Middlesbrough Bus Station Express Lounge',  'Leeds City Centre Bus Stn',
            'Shudehill Interchange', 'Leeds City Centre York Street', 'Meadowhall Interchange',
            'Nottingham Broad Marsh Bus Station', 'Loughborough Holywell Way', 'Fosse Park ASDA',
            'Rugby ASDA', '049004705400', 'Victoria Coach Station Arrivals'
        ])

        with override_settings(TNDS_DIR='this is not a directory'):
            # should not be cached (because dummy cache)
            with override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}}):
                res = self.client.get(self.gb_m12.get_absolute_url())
                self.assertEqual([], res.context_data['timetables'])

            # should be cached
            res = self.client.get(self.gb_m12.get_absolute_url())
            self.assertEqual('2017-01-01', str(res.context_data['timetables'][0].date))

            # should be cached (even though different date)
            res = self.client.get(self.gb_m12.get_absolute_url() + '?date=2017-01-02')
            self.assertEqual('2017-01-02', str(res.context_data['timetables'][0].date))

    @freeze_time('25 June 2016')
    def test_do_service_scotland(self):
        service = self.sc_service

        self.assertEqual(str(service), 'N17 - Aberdeen - Dyce')
        self.assertTrue(service.show_timetable)
        self.assertEqual(service.operator.first(), self.fabd)
        self.assertEqual(
            service.get_traveline_link()[0],
            'http://www.travelinescotland.com/lts/#/timetables?' +
            'timetableId=ABBN017&direction=OUTBOUND&queryDate=&queryTime='
        )
        self.assertEqual(service.geometry.coords, ((
            (53.7423055225, -2.504212506), (53.7398252112, -2.5083672338),
            (53.7389877672, -2.5108434749), (53.7425523688, -2.4989239373)
        ),))

        res = self.client.get(service.get_absolute_url())
        self.assertEqual(res.context_data['breadcrumb'], [self.sc, self.fabd])
        self.assertTemplateUsed(res, 'busstops/service_detail.html')
        self.assertContains(res, '<td colspan="5" rowspan="63">then every 30 minutes until</td>', html=True)

        # Within operating period, but with no journeys
        res = self.client.get(service.get_absolute_url() + '?date=2026-04-18')
        self.assertContains(res, 'Sorry, no journeys found for Saturday 18 April 2026')

        # Test the fallback version without a timetable (just a list of stops)
        service.show_timetable = False
        service.save()
        res = self.client.get(service.get_absolute_url())
        self.assertContains(res, 'Outbound')
        self.assertContains(res, """
            <li class="OTH" itemscope itemtype="https://schema.org/BusStop">
                <a href="/stops/639004554">
                    <span itemprop="name">Witton Park (opp)</span>
                    <span itemprop="geo" itemscope itemtype="https://schema.org/GeoCoordinates">
                        <meta itemprop="latitude" content="-2.5108434749" />
                        <meta itemprop="longitude" content="53.7389877672" />
                    </span>
                </a>
            </li>
        """, html=True)

    @freeze_time('25 June 2016')
    def test_do_service_wales(self):
        service = Service.objects.get(service_code='CGAO305')
        service_code = service.servicecode_set.first()

        self.assertEqual(service_code.scheme, 'Traveline Cymru')
        self.assertEqual(service_code.code, '305MFMWA1')

        service.region = self.w
        service.source = None
        service.save()

        response = self.client.get(service.get_absolute_url())
        self.assertEqual(response.context_data['links'], [{
            'url': 'https://www.traveline.cymru/timetables/?routeNum=305&direction_id=0&timetable_key=305MFMWA1',
            'text': 'Timetable on the Traveline Cymru website'
        }])

    def test_departures(self):
        self.assertEqual(6, Journey.objects.filter(service='M12_MEGA').count())
        self.assertEqual(9, StopUsageUsage.objects.filter(journey__service='M12_MEGA').count())

        # Megabus services have been imported twice, but there should only be one of each StopUsage
        self.assertEqual(1, StopPoint.objects.filter(service='M12_MEGA').count())

        # This should be the first journey (some earlier journeys should have been deleted)
        journey = Journey.objects.first()
        self.assertEqual('M12 - Shudehill - Victoria 2017-01-01 01:00:00+00:00', str(journey))

        stop_usage_usage = StopUsageUsage.objects.first()
        self.assertEqual('2017-01-01 02:20:00+00:00', str(stop_usage_usage.datetime))
        self.assertEqual('Kingston District Centre (o/s) 2017-01-01 02:20:00+00:00', str(stop_usage_usage))

        self.assertEqual(0, Journey.objects.filter(service__region='S').count())
        self.assertEqual(0, Journey.objects.filter(service__region='EA').count())

    def test_combine_date_time(self):
        combine_date_time = generate_departures.combine_date_time
        self.assertEqual(str(combine_date_time(date(2017, 3, 26), time(0, 10))), '2017-03-26 00:10:00+00:00')
        # Clocks go forward 1 hour at 1am. Not sure what buses *actually* do, but pretending
        self.assertEqual(str(combine_date_time(date(2017, 3, 26), time(1, 10))), '2017-03-26 02:10:00+01:00')
        self.assertEqual(str(combine_date_time(date(2017, 3, 27), time(0, 10))), '2017-03-27 00:10:00+01:00')

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        clean_up()

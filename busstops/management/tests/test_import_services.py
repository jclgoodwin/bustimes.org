import os
import xml.etree.cElementTree as ET
import zipfile
import warnings
from freezegun import freeze_time
from django.test import TestCase, override_settings
from django.contrib.gis.geos import Point
from django.core.management import call_command
from bustimes.management.commands import import_transxchange
from ...models import Operator, DataSource, OperatorCode, Service, Region, StopPoint, ServiceLink


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

    command = import_transxchange.Command()

    @classmethod
    @freeze_time('2016-01-01')
    def setUpTestData(cls):
        clean_up()

        cls.gb = Region.objects.create(pk='GB', name='Großbritannien')
        cls.sc = Region.objects.create(pk='S', name='Scotland')
        cls.nw = Region.objects.create(pk='NW', name='North West')
        cls.w = Region.objects.create(pk='W', name='Wales')
        cls.london = Region.objects.create(pk='L', name='London')

        cls.megabus = Operator.objects.create(pk='MEGA', region_id='GB', name='Megabus')
        cls.fabd = Operator.objects.create(pk='FABD', region_id='S', name='First Aberdeen')

        nocs = DataSource.objects.create(name='National Operator Codes', datetime='2018-02-01 00:00+00:00')
        OperatorCode.objects.create(operator=cls.megabus, source=nocs, code='MEGA')
        OperatorCode.objects.create(operator=cls.fabd, source=nocs, code='FABD')

        StopPoint.objects.bulk_create(
            StopPoint(
                atco_code=atco_code, locality_centre=False, active=True, common_name=common_name,
                indicator=indicator, latlong=Point(lng, lat, srid=4326)
            ) for atco_code, common_name, indicator, lat, lng in (
                    ('639004572', 'Bulls Head', 'adj', -2.5042125060, 53.7423055225),
                    ('639004562', 'Markham Road', 'by"', -2.5083672338, 53.7398252112),
                    ('639004554', 'Witton Park', 'opp', -2.5108434749, 53.7389877672),
                    ('639004552', 'The Griffin', 'adj', -2.4989239373, 53.7425523688),
                    ('049004705400', 'Kingston District Centre', 'o/s', 0, 0),
                    ('1000DDDV4248', 'Dinting Value Works', '', 0, 0),
            )
        )

        # simulate a Scotland zipfile:
        cls.write_files_to_zipfile_and_import('S.zip', ['SVRABBN017.xml'])

        # simulate a North West zipfile:
        cls.write_files_to_zipfile_and_import('NW.zip', ['NW_04_GMN_2_1.xml', 'NW_04_GMN_2_2.xml',
                                                         'NW_04_GMS_237_1.xml', 'NW_04_GMS_237_2.xml'])

        cls.sc_service = Service.objects.get(service_code='ABBN017')

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

        cls.gb_m11a = Service.objects.get(service_code='M11A_MEGA')
        cls.gb_m12 = Service.objects.get(service_code='M12_MEGA')

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

    # def test_sanitize_description(self):
    #     testcases = (
    #         (
    #             'Bus Station bay 5,Blyth - Grange Road turning circle,Widdrington Station',
    #             'Blyth - Widdrington Station'
    #         ),
    #         (
    #             '      Bus Station-Std C,Winlaton - Ryton Comprehensive School,Ryton     ',
    #             'Winlaton - Ryton'
    #         ),
    #     )

    #     for inp, outp in testcases:
    #         self.assertEqual(self.command.sanitize_description(inp), outp)

    def test_get_service_code(self):
        self.assertEqual(import_transxchange.get_service_code('ea_21-2-_-y08-1.xml'),     'ea_21-2-_-y08')
        self.assertEqual(import_transxchange.get_service_code('ea_21-27-D-y08-1.xml'),    'ea_21-27-D-y08')
        self.assertEqual(import_transxchange.get_service_code('tfl_52-FL2-_-y08-1.xml'),  'tfl_52-FL2-_-y08')
        self.assertEqual(import_transxchange.get_service_code('suf_56-FRY-1-y08-15.xml'), 'suf_56-FRY-1-y08')
        self.assertIsNone(import_transxchange.get_service_code('NATX_330.xml'))
        self.assertIsNone(import_transxchange.get_service_code('NE_130_PB2717_21A.xml'))
        self.assertIsNone(import_transxchange.get_service_code('SVRABAN007-20150620-9.xml'))
        self.assertIsNone(import_transxchange.get_service_code('SVRWLCO021-20121121-13693.xml'))
        self.assertIsNone(import_transxchange.get_service_code('National Express_NX_atco_NATX_T61.xml'))
        self.assertIsNone(import_transxchange.get_service_code('SnapshotNewportBus_TXC_2015714-0317_NTAO155.xml'))
        self.assertIsNone(import_transxchange.get_service_code(
            'ArrivaCymru51S-Rhyl-StBrigid`s-Denbigh1_TXC_2016108-0319_DGAO051S.xml')
        )

    def test_get_operator_name(self):
        blue_triangle_element = ET.fromstring("""
            <txc:Operator xmlns:txc='http://www.transxchange.org.uk/' id='OId_BE'>
                <txc:OperatorCode>BE</txc:OperatorCode>
                <txc:OperatorShortName>BLUE TRIANGLE BUSES LIM</txc:OperatorShortName>
                <txc:OperatorNameOnLicence>BLUE TRIANGLE BUSES LIMITED</txc:OperatorNameOnLicence>
                <txc:TradingName>BLUE TRIANGLE BUSES LIMITED</txc:TradingName>
            </txc:Operator>
        """)
        self.assertEqual(import_transxchange.get_operator_name(blue_triangle_element), 'BLUE TRIANGLE BUSES LIMITED')

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
            self.assertTrue('Operator not found:' in str(caught_warnings[0].message))

    @classmethod
    def do_service(cls, filename, region_id):
        filename = '%s.xml' % filename
        if region_id == 'GB':
            region_id = 'NCSD'
        cls.command.set_region('%s.zip' % region_id)
        path = os.path.join(FIXTURES_DIR, filename)
        with open(path) as xml_file:
            cls.command.handle_file(xml_file, filename)

    def test_do_service_invalid(self):
        """A file with some wrong references should be silently ignored"""
        with self.assertLogs(level='ERROR'):
            self.do_service('NW_05_PBT_6_1', 'GB')

    def test_service_nw(self):
        # 2
        service = Service.objects.get(service_code='NW_04_GMN_2_1')
        self.assertEqual(service.description, 'intu Trafford Centre - Eccles - Swinton - Bolton')

        self.assertEqual(23, service.stopusage_set.all().count())

    def test_service_nw_2(self):
        # Stagecoach Manchester 237
        service = Service.objects.get(service_code='NW_04_GMS_237_1')
        duplicate = Service.objects.get(service_code='NW_04_GMS_237_2')
        ServiceLink.objects.create(from_service=service, to_service=duplicate, how='parallel')

        self.assertEqual(service.description, 'Glossop - Stalybridge - Ashton')

        with freeze_time('1 September 2017'):
            with self.assertNumQueries(11):
                res = self.client.get(service.get_absolute_url() + '?date=2017-09-01')
        self.assertEqual(str(res.context_data['timetable'].date), '2017-09-01')
        self.assertContains(res, 'Timetable changes from Sunday 3 September 2017')

        with freeze_time('1 October 2017'):
            with self.assertNumQueries(14):
                res = self.client.get(service.get_absolute_url())  # + '?date=2017-10-01')
        self.assertContains(res, """
                <thead>
                    <tr>
                        <td></td>
                        <td>237</td>
                        <td colspan="17"><a href="/services/237-glossop-stalybridge-ashton-2">237</a></td>
                    </tr>
                </thead>
        """, html=True)
        self.assertEqual(str(res.context_data['timetable'].date), '2017-10-01')
        self.assertNotContains(res, 'Timetable changes from Sunday 3 September 2017')
        self.assertEqual(18, len(res.context_data['timetable'].groupings[0].trips))

        with freeze_time('1 October 2017'):
            with self.assertNumQueries(14):
                res = self.client.get(service.get_absolute_url() + '?date=2017-10-03')
        self.assertNotContains(res, 'thead')
        self.assertEqual(str(res.context_data['timetable'].date), '2017-10-03')
        self.assertEqual(27, len(res.context_data['timetable'].groupings[0].trips))
        self.assertEqual(30, len(res.context_data['timetable'].groupings[1].trips))

        self.assertEqual(87, service.stopusage_set.all().count())
        self.assertEqual(121, duplicate.stopusage_set.all().count())

    @freeze_time('22 January 2017')
    def test_do_service_m11a(self):
        res = self.client.get('/services/m11a-belgravia-liverpool?date=ceci n\'est pas une date')

        service = res.context_data['object']

        self.assertEqual(str(service), 'M11A - Belgravia - Liverpool')
        self.assertTrue(service.show_timetable)
        self.assertEqual(service.operator.first(), self.megabus)
        self.assertEqual(
            list(service.get_traveline_links()),
            [('http://www.travelinesoutheast.org.uk/se/XSLT_TTB_REQUEST' +
             '?line=11M11&sup=A&net=nrc&project=y08&command=direct&outputFormat=0', 'Traveline')]
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
        self.assertContains(res, '/js/timetable.min.js')

        timetable = res.context_data['timetable']
        self.assertFalse(timetable.groupings[0].has_minor_stops())
        self.assertFalse(timetable.groupings[1].has_minor_stops())
        self.assertEqual(str(timetable.groupings[1].rows[0].times), '[13:00, 15:00, 16:00, 16:30, 18:00, 20:00, 23:45]')

        # should only be 6, despite running 'import_services' twice
        self.assertEqual(6, service.stopusage_set.count())

    @freeze_time('1 Jan 2017')
    def test_do_service_m12(self):
        res = self.client.get(self.gb_m12.get_absolute_url())

        self.assertContains(res, '<option selected value="2017-01-01">Sunday 1 January 2017</option>')

        groupings = res.context_data['timetable'].groupings
        self.assertEqual(len(groupings[0].rows), 15)
        self.assertEqual(len(groupings[1].rows), 15)
        self.assertContains(res, """
            <tr>
                <th><a href="/stops/450030220">Leeds City Centre Bus Stn</a></th>
                <td></td><td>06:15</td><td rowspan="2">09:20</td><td rowspan="2">10:20</td><td></td><td></td><td></td>
                <td></td><td></td><td rowspan="2"></td>
            </tr>
        """, html=True)
        self.assertContains(res, """
            <tr class="dep">
                <th><a href="/stops/450030220">Leeds City Centre Bus Stn</a></th>
                <td>02:45</td><td>06:20</td><td>11:30</td><td>12:30</td><td>13:45</td><td>16:20</td><td>18:40</td>
            </tr>
        """, html=True)

    @freeze_time('25 June 2016')
    def test_do_service_scotland(self):
        service = self.sc_service

        self.assertEqual(str(service), 'N17 - Aberdeen - Dyce')
        self.assertTrue(service.show_timetable)
        self.assertEqual(service.operator.first(), self.fabd)
        self.assertEqual(
            list(service.get_traveline_links()),
            [('http://www.travelinescotland.com/lts/#/timetables?' +
             'timetableId=ABBN017&direction=OUTBOUND&queryDate=&queryTime=', 'Traveline Scotland')]
        )
        self.assertEqual(service.geometry.coords, ((
            (53.7423055225, -2.504212506), (53.7398252112, -2.5083672338),
            (53.7389877672, -2.5108434749), (53.7425523688, -2.4989239373)
        ),))

        res = self.client.get(service.get_absolute_url())
        self.assertEqual(res.context_data['breadcrumb'], [self.sc, self.fabd])
        self.assertTemplateUsed(res, 'busstops/service_detail.html')
        self.assertContains(res, '<td rowspan="63">then every 30 minutes until</td>', html=True)

        timetable = res.context_data['timetable']
        self.assertEqual('2016-06-25', str(timetable.date))
        self.assertEqual(3, len(timetable.groupings[0].rows[0].times))
        self.assertEqual(3, len(timetable.groupings[1].rows[0].times))
        self.assertEqual(timetable.groupings[0].column_feet, {})

        # Within operating period, but with no journeys
        res = self.client.get(service.get_absolute_url() + '?date=2026-04-18')
        self.assertContains(res, 'Sorry, no journeys found for Saturday 18 April 2026')

        # Test the fallback version without a timetable (just a list of stops)
        service.show_timetable = False
        service.save()
        res = self.client.get(service.get_absolute_url())
        self.assertContains(res, 'Outbound')
        self.assertContains(res, """
            <li class="minor">
                <a href="/stops/639004554">Witton Park (opp)</a>
            </li>
        """, html=True)

    # def test_combine_date_time(self):
    #     combine_date_time = generate_departures.combine_date_time
    #     self.assertEqual(str(combine_date_time(date(2017, 3, 26), time(0, 10))), '2017-03-26 00:10:00+00:00')
    #     # Clocks go forward 1 hour at 1am. Not sure what buses *actually* do, but pretending
    #     self.assertEqual(str(combine_date_time(date(2017, 3, 26), time(1, 10))), '2017-03-26 02:10:00+01:00')
    #     self.assertEqual(str(combine_date_time(date(2017, 3, 27), time(0, 10))), '2017-03-27 00:10:00+01:00')

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        clean_up()

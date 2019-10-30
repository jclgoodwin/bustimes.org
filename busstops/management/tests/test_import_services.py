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
                    ('4200F156472', 'Asda', 'opp', 0, 0),
                    ('2900A1820', 'Leys Lane', 'adj', 0, 0),
                    ('1000DDDV4248', 'Dinting Value Works', '', 0, 0),
            )
        )

        StopPoint.objects.bulk_create(
            StopPoint(atco_code, active=True) for atco_code in (
                '639006355',
                '639004802',
                '1800EB00011',
                '1800SB08951',
                '1800BNIN001',
                '1800TCBS001',
                '1000DGHS0900',
                '1800ANBS001',
                '1000DGSD4386',
                '1000DGHS1150',
                '490016736W',
                '1800SHIC0G1',
                '2800S42098F',
                '450030220',
                '41000008NC67',
                '4100024PARWS',
                '450017207',
                '3390BB01',
                '1100DEB10368',
                '1100DEC10085',
                '1100DEC10720',
                '1100DEB10354',
                '5230WDB25331',
                '2900A181',
                '2900S367',
                '2900N12106',
                # '0500HSTIV002'
            )
        )

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
            self.assertEqual(import_transxchange.infer_from_filename(filename), parts)

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
        self.do_service('NW_05_PBT_6_1', 'GB')

    @freeze_time('30 October 2017')
    def test_do_service_with_empty_pattern(self):
        """A file with a JourneyPattern with no JourneyPatternSections should be imported"""
        with warnings.catch_warnings(record=True) as caught_warnings:
            self.do_service('swe_33-9A-A-y10-2', 'GB')
            # self.assertEqual(len(caught_warnings), 2)
            print(caught_warnings)
        self.assertTrue(Service.objects.filter(service_code='swe_33-9A-A-y10').exists())

    def test_service_nw(self):
        # 2
        service = Service.objects.get(service_code='NW_04_GMN_2_1')
        self.assertEqual(service.description, 'intu Trafford Centre - Eccles - Swinton - Bolton')

        self.assertEqual(2, service.stopusage_set.all().count())

    def test_service_nw_2(self):
        # Stagecoach Manchester 237
        service = Service.objects.get(service_code='NW_04_GMS_237_1')
        duplicate = Service.objects.get(service_code='NW_04_GMS_237_2')
        ServiceLink.objects.create(from_service=service, to_service=duplicate, how='parallel')

        self.assertEqual(service.description, 'Glossop - Stalybridge - Ashton')

        with freeze_time('1 September 2017'):
            res = self.client.get(service.get_absolute_url())
        self.assertContains(res, 'Timetable changes from Sunday 3 September 2017')

        with freeze_time('1 October 2017'):
            res = self.client.get(service.get_absolute_url())

        self.assertNotContains(res, 'Timetable changes from Sunday 3 September 2017')

        self.assertEqual(18, len(res.context_data['timetable'].groupings[0].journeys))

        with freeze_time('1 October 2017'):
            res = self.client.get(service.get_absolute_url() + '?date=2017-10-03')
        self.assertEqual(27, len(res.context_data['timetable'].groupings[0].journeys))
        self.assertEqual(30, len(res.context_data['timetable'].groupings[1].journeys))

        self.assertEqual(1, service.stopusage_set.all().count())
        self.assertEqual(6, duplicate.stopusage_set.all().count())

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
                <th>2900N12345</th><td>19:48</td><td>22:56</td>
            </tr>
        """, html=True)
        self.assertContains(res, '<option selected value="2016-10-03">Monday 3 October 2016</option>')

        # Test the fallback version without a timetable (just a list of stops)
        service.show_timetable = False
        service.save()
        res = self.client.get(service.get_absolute_url())
        self.assertContains(res, 'Leys Lane (adj)')
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
        self.assertContains(res, '/js/timetable.min.js')

    @freeze_time('1 Jan 2017')
    def test_do_service_m12(self):
        res = self.client.get(self.gb_m12.get_absolute_url())

        self.assertContains(res, '<option selected value="2017-01-01">Sunday 1 January 2017</option>')

        groupings = res.context_data['timetable'].groupings
        self.assertEqual(len(groupings[0].rows), 15)
        self.assertEqual(len(groupings[1].rows), 15)

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
        self.assertContains(res, '<td rowspan="63">then every 30 minutes until</td>', html=True)

        # Within operating period, but with no journeys
        res = self.client.get(service.get_absolute_url() + '?date=2026-04-18')
        self.assertContains(res, 'Sorry, no journeys found for Saturday 18 April 2026')

        # Test the fallback version without a timetable (just a list of stops)
        service.show_timetable = False
        service.save()
        res = self.client.get(service.get_absolute_url())
        self.assertContains(res, 'Outbound')
        self.assertContains(res, """
            <li class="OTH">
                <a href="/stops/639004554">Witton Park (opp)</a>
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

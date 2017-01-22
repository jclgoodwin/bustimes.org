# coding=utf-8
import os
import xml.etree.cElementTree as ET
import zipfile
import warnings
from freezegun import freeze_time
from django.test import TestCase, override_settings
from django.contrib.gis.geos import Point
from django.core.management import call_command
from ...models import Operator, Service, Region, StopPoint
from ..commands import import_services


FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'fixtures')


class ImportServicesTest(TestCase):
    "Tests for parts of the command that imports services from TNDS"

    command = import_services.Command()

    @classmethod
    @override_settings(TNDS_DIR=FIXTURES_DIR)
    def setUpTestData(cls):
        cls.ea = Region.objects.create(pk='EA', name='East Anglia')
        cls.gb = Region.objects.create(pk='GB', name='Großbritannien')
        cls.sc = Region.objects.create(pk='S', name='Scotland')
        cls.london = Region.objects.create(pk='L', name='London')

        cls.fecs = Operator.objects.create(pk='FECS', region_id='EA', name='First in Norfolk & Suffolk')
        cls.megabus = Operator.objects.create(pk='MEGA', region_id='GB', name='Megabus')
        cls.fabd = Operator.objects.create(pk='FABD', region_id='S', name='First Aberdeen')
        cls.blue_triangle_element = ET.fromstring("""
            <txc:Operator xmlns:txc='http://www.transxchange.org.uk/' id='OId_BE'>
                <txc:OperatorCode>BE</txc:OperatorCode>
                <txc:OperatorShortName>BLUE TRIANGLE BUSES LIM</txc:OperatorShortName>
                <txc:OperatorNameOnLicence>BLUE TRIANGLE BUSES LIMITED</txc:OperatorNameOnLicence>
                <txc:TradingName>BLUE TRIANGLE BUSES LIMITED</txc:TradingName>
            </txc:Operator>
        """)
        cls.bakers_dolphin = Operator.objects.create(pk='BAKE', region_id='S',
                                                     name='Bakers Dolphin')
        cls.bakers_porpoise = Operator.objects.create(pk='DOLP', region_id='S',
                                                      name='Bakers Porpoise')

        for atco_code, common_name, indicator, lat, lng in (
                ('639004572', 'Bulls Head', 'adj', -2.5042125060, 53.7423055225),
                ('639004562', 'Markham Road', 'by"', -2.5083672338, 53.7398252112),
                ('639004554', 'Witton Park', 'opp', -2.5108434749, 53.7389877672),
                ('639004552', 'The Griffin', 'adj', -2.4989239373, 53.7425523688)
        ):
            StopPoint.objects.create(
                atco_code=atco_code, locality_centre=False, active=True, common_name=common_name,
                indicator=indicator, latlong=Point(lng, lat, srid=4326)
            )

        cls.do_service('ea_21-13B-B-y08-1', 'EA')
        cls.ea_service = Service.objects.get(pk='ea_21-13B-B-y08')
        cls.do_service('SVRABBN017', 'S')
        cls.sc_service = Service.objects.get(pk='ABBN017')

        # simulate a National Coach Service Database zip file
        ncsd_zipfile_path = os.path.join(FIXTURES_DIR, 'NCSD.zip')
        with zipfile.ZipFile(ncsd_zipfile_path, 'a') as ncsd_zipfile:
            cls.write_file_to_zipfile(ncsd_zipfile, 'Megabus_Megabus14032016 163144_MEGA_M11A.xml')
            cls.write_file_to_zipfile(ncsd_zipfile, 'Megabus_Megabus14032016 163144_MEGA_M12.xml')
            ncsd_zipfile.writestr(
                'IncludedServices.csv',
                'Operator,LineName,Description\nMEGA,M11A,Belgravia - Liverpool\nMEGA,M12,Shudehill - Victoria'
            )
        call_command(cls.command, ncsd_zipfile_path)

        # test re-importing a previously imported service again
        cls.do_service('Megabus_Megabus14032016 163144_MEGA_M12', 'GB')

        cls.gb_m11a = Service.objects.get(pk='M11A_MEGA')
        cls.gb_m12 = Service.objects.get(pk='M12_MEGA')

    @staticmethod
    def write_file_to_zipfile(open_zipfile, filename):
        open_zipfile.write(os.path.join(FIXTURES_DIR, filename),
                           os.path.join('NCSD_TXC', filename))

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
        self.assertEqual(self.command.get_operator_name(self.blue_triangle_element), 'BLUE TRIANGLE BUSES LIMITED')

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

        # test SPECIAL_OPERATOR_TRADINGNAMES
        self.assertEqual('BTRI', self.command.get_operator(self.blue_triangle_element))

        self.assertEqual('RJWS', self.command.get_operator(ET.fromstring("""
            <txc:Operator id="OId_RJW" xmlns:txc="http://www.transxchange.org.uk/">
                <txc:OperatorCode>RJW</txc:OperatorCode>
                <txc:OperatorShortName>R. J's of Wem</txc:OperatorShortName>
                <txc:OperatorNameOnLicence>R. J's of Wem</txc:OperatorNameOnLicence>
                <txc:TradingName>R. J's of Wem</txc:TradingName>
            </txc:Operator>
        """)))

        with warnings.catch_warnings(record=True) as collected_warnings:
            self.assertIsNone(self.command.get_operator(ET.fromstring("""
                <txc:Operator xmlns:txc="http://www.transxchange.org.uk/" id="OId_RRS">
                    <txc:OperatorCode>BEAN</txc:OperatorCode>
                    <txc:TradingName>Bakers</txc:TradingName>
                </txc:Operator>
            """)))
            self.assertTrue('No operator found for element' in str(collected_warnings[0].message))

        self.assertEqual(self.bakers_dolphin.id, self.command.get_operator(ET.fromstring("""
            <txc:Operator xmlns:txc="http://www.transxchange.org.uk/" id="OId_RRS">
                <txc:OperatorCode>BEAN</txc:OperatorCode>
                <txc:TradingName>Bakers D</txc:TradingName>
            </txc:Operator>
        """)))

        self.assertEqual('YTIG', self.command.get_operator(ET.fromstring("""
            <txc:Operator xmlns:txc="http://www.transxchange.org.uk/">
                <txc:OperatorCode>HBSY</txc:OperatorCode>
            </txc:Operator>
        """)))

    def test_get_line_name_and_brand(self):
        with warnings.catch_warnings(record=True) as caught_warnings:
            element = ET.fromstring("""<txc:Service xmlns:txc="http://www.transxchange.org.uk/"><txc:Lines><txc:Line>
                <txc:LineName>Llanfairpwllgwyngyllgogerychwyrndrobwllllantysiliogogogoch Park &amp; Ride</txc:LineName>
                </txc:Line></txc:Lines></txc:Service>""")
            line_name_and_brand = self.command.get_line_name_and_brand(element, None)
            self.assertEqual(line_name_and_brand,
                             ('Llanfairpwllgwyngyllgogerychwyrndrobwllllantysiliogogogoch Park ', ''))
            self.assertTrue('too long in' in str(caught_warnings[0].message))

    @classmethod
    def do_service(cls, filename, region_id):
        filename = '%s.xml' % filename
        if region_id == 'GB':
            cls.command.set_region('NCSD.zip')
        else:
            cls.command.set_region('%s.zip' % region_id)
        path = os.path.join(FIXTURES_DIR, filename)
        with open(path) as xml_file:
            cls.command.do_service(xml_file, filename)

    @freeze_time('1 October 2016')
    @override_settings(TNDS_DIR=FIXTURES_DIR)
    def test_do_service_ea(self):
        service = self.ea_service

        self.assertEqual(str(service), '13B - Turquoise Line - Norwich - Wymondham - Attleborough')
        self.assertEqual(service.line_name, '13B')
        self.assertEqual(service.line_brand, 'Turquoise Line')
        self.assertTrue(service.show_timetable)
        self.assertEqual(service.outbound_description, 'Norwich - Wymondham - Attleborough')
        self.assertEqual(service.inbound_description, 'Attleborough - Wymondham - Norwich')
        self.assertEqual(service.operator.first(), self.fecs)
        self.assertEqual(
            service.get_traveline_url(),
            'http://www.travelinesoutheast.org.uk/se/XSLT_TTB_REQUEST' +
            '?line=2113B&lineVer=1&net=ea&project=y08&sup=B&command=direct&outputFormat=0'
        )

        res = self.client.get(service.get_absolute_url())
        self.assertEqual(res.context_data['breadcrumb'], (self.ea, self.fecs))
        # self.assertContains(res, """
        #     <tr class="OTH">
        #         <th>Norwich Brunswick Road</th>
        #         <td>19:48</td><td>19:48</td><td>22:56</td><td>22:56</td>
        #         <td>08:57</td><td>09:57</td><td>10:57</td><td>17:57</td>
        #     </tr>
        # """, html=True)

    @override_settings(TNDS_DIR=FIXTURES_DIR)
    @freeze_time('22 January 2017')
    def test_do_service_m11a(self):
        res = self.client.get('/services/M11A_MEGA')

        service = res.context_data['object']

        self.assertEqual(str(service), 'M11A - Belgravia - Liverpool')
        self.assertTrue(service.show_timetable)
        self.assertEqual(service.operator.first(), self.megabus)
        self.assertEqual(
            service.get_traveline_url(),
            'http://www.travelinesoutheast.org.uk/se/XSLT_TTB_REQUEST' +
            '?line=11M11A&net=nrc&project=y08&command=direct&outputFormat=0'
        )

        self.assertEqual(res.context_data['breadcrumb'], (self.gb, self.megabus))
        self.assertTemplateUsed(res, 'busstops/service_detail.html')
        self.assertContains(res, '<h1>M11A - Belgravia - Liverpool</h1>', html=True)
        self.assertContains(
            res,
            """
            <td colspan="7">
            Book at <a
            href="https://www.awin1.com/awclick.php?mid=2678&amp;id=242611&amp;clickref=notes" rel="nofollow">
            megabus.com</a> or 0900 1600900 (65p/min + network charges)
            </td>
            """,
            html=True
        )

    @override_settings(TNDS_DIR=FIXTURES_DIR)
    def test_do_service_m12(self):
        res = self.client.get('/services/M12_MEGA?date=2017-01-15')
        groupings = res.context_data['timetables'][0].groupings
        outbound_stops = [str(row.part.stop) for row in groupings[0].rows]
        inbound_stops = [str(row.part.stop) for row in groupings[1].rows]
        self.assertEqual(outbound_stops, [
            'Belgravia Victoria Coach Station', '049004705400', 'Rugby ASDA',
            'Fosse Park ASDA', 'Loughborough Holywell Way', 'Nottingham Broad Marsh Bus Station',
            'Meadowhall Interchange', 'Leeds City Centre York Street',
            'Bradford City Centre Hall Ings', 'Huddersfield Town Centre Market Street',
            'Leeds City Centre Bus Stn', 'Middlesbrough Bus Station Express Lounge',
            'Sunderland Interchange', 'Newcastle upon Tyne John Dobson Street',
            'Shudehill Interchange'
        ])
        self.assertEqual(inbound_stops, [
            'Newcastle upon Tyne John Dobson Street', 'Sunderland Interchange',
            'Middlesbrough Bus Station Express Lounge', 'Huddersfield Town Centre Market Street',
            'Bradford City Centre Interchange', 'Leeds City Centre Bus Stn',
            'Shudehill Interchange', 'Leeds City Centre York Street', 'Meadowhall Interchange',
            'Nottingham Broad Marsh Bus Station', 'Loughborough Holywell Way', 'Fosse Park ASDA',
            'Rugby ASDA', '049004705400', 'Victoria Coach Station Arrivals'
        ])

    @override_settings(TNDS_DIR=FIXTURES_DIR)
    def test_do_service_scotland(self):
        service = self.sc_service

        self.assertEqual(str(service), 'N17 - Aberdeen - Dyce')
        self.assertTrue(service.show_timetable)
        self.assertEqual(service.operator.first(), self.fabd)
        self.assertEqual(
            service.get_traveline_url(),
            'http://www.travelinescotland.com/lts/#/timetables?' +
            'timetableId=ABBN017&direction=OUTBOUND&queryDate=&queryTime='
        )
        self.assertEqual(service.geometry.coords, ((
            (53.7423055225, -2.504212506), (53.7398252112, -2.5083672338),
            (53.7389877672, -2.5108434749), (53.7425523688, -2.4989239373)
        ),))

        res = self.client.get(service.get_absolute_url())
        self.assertEqual(res.context_data['breadcrumb'], (self.sc, self.fabd))
        self.assertTemplateUsed(res, 'busstops/service_detail.html')
        # self.assertContains(res, '<td colspan="5" rowspan="62">then every 30 minutes until</td>', html=True)

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

    @classmethod
    def tearDownClass(cls):
        super(ImportServicesTest, cls).tearDownClass()

        # clean up
        os.remove(os.path.join(FIXTURES_DIR, 'NCSD.zip'))

        return
        for parts in (
                ('EA', 'ea_21-13B-B-y08-1'),
                ('NCSD', 'NCSD_TXC', 'Megabus_Megabus14032016 163144_MEGA_M11A'),
                ('NCSD', 'NCSD_TXC', 'Megabus_Megabus14032016 163144_MEGA_M12'),
                ('NCSD', 'Megabus_Megabus14032016 163144_MEGA_M12'),
                ('S', 'SVRABBN017')
        ):
            os.remove(os.path.join(FIXTURES_DIR, *parts))

        os.rmdir(os.path.join(FIXTURES_DIR, 'EA'))
        os.rmdir(os.path.join(FIXTURES_DIR, 'NCSD/NCSD_TXC'))
        os.rmdir(os.path.join(FIXTURES_DIR, 'NCSD'))
        os.rmdir(os.path.join(FIXTURES_DIR, 'S'))

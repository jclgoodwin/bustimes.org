import os
import zipfile
from freezegun import freeze_time
from django.test import TestCase, override_settings
from django.core.management import call_command
from bustimes.management.commands import import_transxchange
from ...models import Operator, DataSource, OperatorCode, Service, Region


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

        cls.megabus = Operator.objects.create(pk='MEGA', region_id='GB', name='Megabus')

        nocs = DataSource.objects.create(name='National Operator Codes', datetime='2018-02-01 00:00+00:00')
        OperatorCode.objects.create(operator=cls.megabus, source=nocs, code='MEGA')

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

    @classmethod
    def do_service(cls, filename, region_id):
        filename = '%s.xml' % filename
        if region_id == 'GB':
            region_id = 'NCSD'
        cls.command.set_region('%s.zip' % region_id)
        path = os.path.join(FIXTURES_DIR, filename)
        with open(path) as xml_file:
            cls.command.handle_file(xml_file, filename)

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

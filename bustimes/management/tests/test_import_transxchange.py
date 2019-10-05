import os
import zipfile
from datetime import date
from freezegun import freeze_time
from django.test import TestCase, override_settings
from django.core.management import call_command
# from ...models import (Operator, DataSource, OperatorCode, Service, Region, StopPoint, Journey, StopUsageUsage,
#                        ServiceDate, ServiceLink)
from ...models import Route, Trip, Calendar, CalendarDate


FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


def clean_up():
    # clean up
    for filename in ('EA.zip', 'S.zip', 'NCSD.zip', 'NW.zip'):
        path = os.path.join(FIXTURES_DIR, filename)
        if os.path.exists(path):
            os.remove(path)


@override_settings(TNDS_DIR=FIXTURES_DIR)
class ImportTransXChangeTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        clean_up()

    @classmethod
    def write_files_to_zipfile_and_import(cls, zipfile_name, filenames):
        zipfile_path = os.path.join(FIXTURES_DIR, zipfile_name)
        with zipfile.ZipFile(zipfile_path, 'a') as open_zipfile:
            for filename in filenames:
                cls.write_file_to_zipfile(open_zipfile, filename)
        call_command('import_transxchange', zipfile_path)

    @staticmethod
    def write_file_to_zipfile(open_zipfile, filename):
        open_zipfile.write(os.path.join(FIXTURES_DIR, filename), filename)

    @freeze_time('3 October 2016')
    def test_east_anglia(self):
        with self.assertNumQueries(85):
            self.write_files_to_zipfile_and_import('EA.zip', ['ea_21-13B-B-y08-1.xml', 'ea_20-12-_-y08-1.xml'])

        service = Route.objects.get(line_name='13B', line_brand='Turquoise Line')

        self.assertEqual(32, Trip.objects.count())
        self.assertEqual(6, Calendar.objects.count())
        self.assertEqual(8, CalendarDate.objects.count())

        self.assertEqual(str(service), '13B – Turquoise Line – Norwich - Wymondham - Attleborough')
        self.assertEqual(service.line_name, '13B')
        self.assertEqual(service.line_brand, 'Turquoise Line')
        self.assertEqual(service.start_date, date(2016, 4, 18))
        self.assertEqual(service.end_date, date(2016, 10, 21))

        res = self.client.get(service.get_absolute_url())
        self.assertContains(res, '<option selected value="2016-10-03">Monday 3 October 2016</option>')
        self.assertContains(res, """
            <tr>
                <th>2900N12348</th>
                <td>19:47</td>
                <td>22:55</td>
            </tr>
        """, html=True)

        res = self.client.get(service.get_absolute_url() + '?date=2016-10-16')
        timetable = res.context_data['timetable']

        # self.assertEqual('Attleborough - Wymondham - Norwich', str(timetable.groupings[0]))

        # self.assertTrue(timetable.groupings[0].has_minor_stops())
        # self.assertEqual(87, len(timetable.groupings[0].rows))
        # self.assertEqual('Leys Lane', timetable.groupings[0].rows[0].stop)

        # self.assertTrue(timetable.groupings[0].has_minor_stops())
        # self.assertEqual(5, len(timetable.groupings[1].rows[0].times))
        self.assertEqual('', timetable.groupings[0].rows[0].times[-1])

        self.assertEqual(87, len(timetable.groupings[1].rows))
        self.assertEqual(['', '', '', '', '', '', '', ''], timetable.groupings[1].rows[0].times[-8:])

        service = Route.objects.get(line_name='12')
        timetable = res.context_data['timetable']

        # self.assertEqual('Outbound', str(timetable.groupings[0]))
        # self.assertEqual(21, len(timetable.groupings[0].rows))

    #     self.assertEqual('St Ives (Cambs) Bus Station', str(timetable.groupings[0].rows[0])[:29])
    #     self.assertEqual(3, len(timetable.groupings[0].rows[0].times))
    #     self.assertEqual(3, timetable.groupings[0].rows[0].times[1].colspan)
    #     self.assertEqual(21, timetable.groupings[0].rows[0].times[1].rowspan)
    #     self.assertEqual(2, len(timetable.groupings[0].rows[1].times))
    #     self.assertEqual(2, len(timetable.groupings[0].rows[20].times))

    #     self.assertEqual(0, len(timetable.groupings[1].rows))

    #     # with self.assertRaises(IndexError):
    #     #     str(timetable.groupings[1])

        # Test operating profile days of non operation
        res = self.client.get(service.get_absolute_url() + '?date=2016-12-28')
        timetable = res.context_data['timetable']

        self.assertEqual(0, len(timetable.groupings))

    #     # Test bank holiday non operation (Boxing Day)
    #     timetable = txc.timetable_from_filename(FIXTURES_DIR, 'ea_20-12-_-y08-1.xml', date(2016, 12, 26))
    #     self.assertEqual(0, len(timetable.groupings[0].rows[0].times))

    @freeze_time('30 October 2017')
    def test_service_with_no_description_and_empty_pattern(self):
        with self.assertNumQueries(237):
            self.write_files_to_zipfile_and_import('EA.zip', ['swe_33-9A-A-y10-2.xml'])

        service = Route.objects.get(line_name='9A')
        self.assertEqual('9A', str(service))

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        clean_up()

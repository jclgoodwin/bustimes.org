import os
import zipfile
from datetime import date
from freezegun import freeze_time
from django.test import TestCase, override_settings
from django.core.management import call_command
from django.contrib.gis.geos import Point
from busstops.models import Region, StopPoint, Service
from ...models import Route, Trip, Calendar, CalendarDate


FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


@override_settings(TNDS_DIR=FIXTURES_DIR)
class ImportTransXChangeTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ea = Region.objects.create(pk='EA', name='East Anglia')
        cls.w = Region.objects.create(pk='W', name='Wales')

        StopPoint.objects.bulk_create(
            StopPoint(atco_code, latlong=Point(0, 0), active=True) for atco_code in (
                '1100DEB10368',
                '1100DEC10085',
                '1100DEC10720',
                '1100DEB10354',
                '2900A181',
                '2900S367',
                '2900N12106',
                '0500HSTIV002',
                '5230WDB25331',
                '5230AWD71095',
            )
        )

    @classmethod
    def write_files_to_zipfile_and_import(cls, zipfile_name, filenames):
        zipfile_path = os.path.join(FIXTURES_DIR, zipfile_name)
        with zipfile.ZipFile(zipfile_path, 'a') as open_zipfile:
            for filename in filenames:
                cls.write_file_to_zipfile(open_zipfile, filename)
        call_command('import_transxchange', zipfile_path)
        os.remove(zipfile_path)

    @staticmethod
    def write_file_to_zipfile(open_zipfile, filename):
        open_zipfile.write(os.path.join(FIXTURES_DIR, filename), filename)

    @freeze_time('3 October 2016')
    def test_east_anglia(self):
        # with self.assertNumQueries(186):
        self.write_files_to_zipfile_and_import('EA.zip', ['ea_21-13B-B-y08-1.xml', 'ea_20-12-_-y08-1.xml'])

        route = Route.objects.get(line_name='13B', line_brand='Turquoise Line')

        self.assertEqual(32, Trip.objects.count())
        self.assertEqual(6, Calendar.objects.count())
        self.assertEqual(8, CalendarDate.objects.count())

        self.assertEqual(str(route), '13B – Turquoise Line – Norwich - Wymondham - Attleborough')
        self.assertEqual(route.line_name, '13B')
        self.assertEqual(route.line_brand, 'Turquoise Line')
        self.assertEqual(route.start_date, date(2016, 4, 18))
        self.assertEqual(route.end_date, date(2016, 10, 21))

        res = self.client.get(route.service.get_absolute_url())
        self.assertContains(res, '<option selected value="2016-10-03">Monday 3 October 2016</option>')
        self.assertContains(res, """
            <tr class="OTH">
                <th>2900N12348</th>
                <td>19:47</td>
                <td>22:55</td>
            </tr>
        """, html=True)

        res = self.client.get(route.service.get_absolute_url() + '?date=2016-10-16')
        timetable = res.context_data['timetable']

        self.assertEqual('Inbound', str(timetable.groupings[0]))

        self.assertTrue(timetable.groupings[0].has_minor_stops())
        self.assertTrue(timetable.groupings[1].has_minor_stops())

        self.assertEqual(87, len(timetable.groupings[0].rows))
        self.assertEqual(91, len(timetable.groupings[1].rows))

        # self.assertEqual(5, len(timetable.groupings[0].rows[0].times))
        self.assertEqual(4, len(timetable.groupings[0].rows[0].times))
        self.assertEqual(4, len(timetable.groupings[1].rows[0].times))

        self.assertEqual('', timetable.groupings[0].rows[0].times[-1])

        # self.assertEqual(['', '', '', '', '', '', '', ''], timetable.groupings[1].rows[0].times[-8:])

        route = Route.objects.get(line_name='12')

        res = self.client.get(route.service.get_absolute_url())
        timetable = res.context_data['timetable']
        self.assertEqual(1, len(timetable.groupings))
        self.assertEqual(21, len(timetable.groupings[0].rows))

        # Test operating profile days of non operation
        res = self.client.get(route.service.get_absolute_url() + '?date=2016-12-28')
        timetable = res.context_data['timetable']
        self.assertEqual(0, len(timetable.groupings))

        # Test bank holiday non operation (Boxing Day)
        res = self.client.get(route.service.get_absolute_url() + '?date=2016-12-28')
        timetable = res.context_data['timetable']
        self.assertEqual(0, len(timetable.groupings))

    @freeze_time('30 October 2017')
    def test_service_with_no_description_and_empty_pattern(self):
        # with self.assertNumQueries(346):
        self.write_files_to_zipfile_and_import('EA.zip', ['swe_33-9A-A-y10-2.xml'])

        route = Route.objects.get(line_name='9A')
        self.assertEqual('9A', str(route))

        res = self.client.get(route.service.get_absolute_url() + '?date=2016-12-28')
        timetable = res.context_data['timetable']
        self.assertEqual(75, len(timetable.groupings[0].rows))
        self.assertEqual(82, len(timetable.groupings[1].rows))

    @freeze_time('23 January 2017')
    def test_do_service_wales(self):
        """Test a timetable from Wales (with SequenceNumbers on Journeys),
        with a university ServicedOrganisation
        """
        # with self.assertNumQueries(346):
        self.write_files_to_zipfile_and_import('W.zip', ['CGAO305.xml'])

        service = Service.objects.get(service_code='CGAO305')

        service_code = service.servicecode_set.first()
        self.assertEqual(service_code.scheme, 'Traveline Cymru')
        self.assertEqual(service_code.code, '305MFMWA1')

        response = self.client.get(service.get_absolute_url() + '?date=2017-01-23')
        timetable = response.context_data['timetable']
        self.assertEqual('2017-01-23', str(timetable.date))
        self.assertEqual(0, len(timetable.groupings))

        self.assertEqual(response.context_data['links'], [{
            'url': 'https://www.traveline.cymru/timetables/?routeNum=305&direction_id=0&timetable_key=305MFMWA1',
            'text': 'Timetable on the Traveline Cymru website'
        }])

        response = self.client.get(service.get_absolute_url() + '/debug')
        self.assertContains(response, 'Wednesday 12 April 2017 - Tuesday 30 May 2017: True')

        response = self.client.get(service.get_absolute_url() + '?date=2017-04-20')
        timetable = response.context_data['timetable']
        self.assertEqual('2017-04-20', str(timetable.date))
        self.assertEqual(1, len(timetable.groupings))
        self.assertEqual(3, len(timetable.groupings[0].rows[0].times))

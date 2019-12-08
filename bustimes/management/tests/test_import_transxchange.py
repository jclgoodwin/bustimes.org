import os
import zipfile
from datetime import date
from freezegun import freeze_time
from django.test import TestCase, override_settings
from django.core.management import call_command
from django.contrib.gis.geos import Point
from busstops.models import Region, StopPoint, Service, Operator, OperatorCode, DataSource
from ...models import Route, Trip, Calendar, CalendarDate


FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


@override_settings(TNDS_DIR=FIXTURES_DIR)
class ImportTransXChangeTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ea = Region.objects.create(pk='EA', name='East Anglia')
        cls.w = Region.objects.create(pk='W', name='Wales')
        Region.objects.create(pk='NE', name='North East')
        cls.fecs = Operator.objects.create(pk='FECS', region_id='EA', name='First in Norfolk & Suffolk')

        source = DataSource.objects.create(name='EA')
        OperatorCode.objects.create(operator=cls.fecs, source=source, code='FECS')

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
        self.write_files_to_zipfile_and_import('EA.zip', ['ea_20-12-_-y08-1.xml', 'ea_21-13B-B-y08-1.xml'])

        route = Route.objects.get(line_name='12')
        self.assertEqual('12', route.service.line_name)

        res = self.client.get(route.service.get_absolute_url())
        timetable = res.context_data['timetable']
        self.assertEqual(1, len(timetable.groupings))
        self.assertEqual(21, len(timetable.groupings[0].rows))
        self.assertEqual(3, len(timetable.groupings[0].rows[0].times))
        self.assertEqual(3, timetable.groupings[0].rows[0].times[1].colspan)
        self.assertEqual(21, timetable.groupings[0].rows[0].times[1].rowspan)
        self.assertEqual(2, len(timetable.groupings[0].rows[1].times))
        self.assertEqual(2, len(timetable.groupings[0].rows[20].times))

        # Test operating profile days of non operation
        res = self.client.get(route.service.get_absolute_url() + '?date=2016-12-28')
        timetable = res.context_data['timetable']
        self.assertEqual(0, len(timetable.groupings))

        # Test bank holiday non operation (Boxing Day)
        res = self.client.get(route.service.get_absolute_url() + '?date=2016-12-28')
        timetable = res.context_data['timetable']
        self.assertEqual(0, len(timetable.groupings))

        #    __     _____     ______
        #   /  |   / ___ \   | ___  \
        #  /_  |   \/   \ \  | |  \  |
        #    | |       _/ /  | |__/  /
        #    | |      |_  |  | ___  |
        #    | |        \ \  | |  \  \
        #    | |   /\___/ /  | |__/  |
        #   /___\  \_____/   |______/

        route = Route.objects.get(line_name='13B', line_brand='Turquoise Line')

        self.assertEqual(32, Trip.objects.count())
        self.assertEqual(6, Calendar.objects.count())
        self.assertEqual(13, CalendarDate.objects.count())

        self.assertEqual(str(route), '13B – Turquoise Line – Norwich - Wymondham - Attleborough')
        self.assertEqual(route.line_name, '13B')
        self.assertEqual(route.line_brand, 'Turquoise Line')
        self.assertEqual(route.start_date, date(2016, 4, 18))
        self.assertEqual(route.end_date, date(2016, 10, 21))

        service = route.service

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
                <th><a href="/stops/2900N12345">Norwich Brunswick Road</a></th><td>19:48</td><td>22:56</td>
            </tr>
        """, html=True)
        self.assertContains(res, '<option selected value="2016-10-03">Monday 3 October 2016</option>')

        res = self.client.get(service.get_absolute_url())
        self.assertContains(res, '<option selected value="2016-10-03">Monday 3 October 2016</option>')
        self.assertContains(res, """
            <tr class="OTH">
                <th><a href="/stops/2900N12348">Norwich Eagle Walk</a></th>
                <td>19:47</td>
                <td>22:55</td>
            </tr>
        """, html=True)

        res = self.client.get(service.get_absolute_url() + '?date=2016-10-16')
        timetable = res.context_data['timetable']

        self.assertEqual('Inbound', str(timetable.groupings[0]))

        self.assertTrue(timetable.groupings[0].has_minor_stops())
        self.assertTrue(timetable.groupings[1].has_minor_stops())

        self.assertEqual(87, len(timetable.groupings[0].rows))
        self.assertEqual(91, len(timetable.groupings[1].rows))

        self.assertEqual(5, len(timetable.groupings[0].rows[0].times))
        self.assertEqual(4, len(timetable.groupings[1].rows[0].times))

        self.assertEqual('', timetable.groupings[0].rows[0].times[-1])

        # self.assertEqual(['', '', '', '', '', '', '', ''], timetable.groupings[1].rows[0].times[-8:])

        # Test the fallback version without a timetable (just a list of stops)
        service.show_timetable = False
        service.save(update_fields=['show_timetable'])
        res = self.client.get(service.get_absolute_url())
        self.assertContains(res, """<li class="PTP">
            <a href="/stops/2900A181"></a>
        </li>""")
        self.assertContains(res, 'Norwich - Wymondham - Attleborough')
        self.assertContains(res, 'Attleborough - Wymondham - Norwich')

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
        # self.assertEqual(0, len(timetable.groupings))

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

    @freeze_time('2016-12-15')
    def test_timetable_ne(self):
        """Test timetable with some abbreviations"""
        self.write_files_to_zipfile_and_import('NE.zip', ['NE_03_SCC_X6_1.xml'])
        service = Service.objects.get()
        response = self.client.get(service.get_absolute_url())
        timetable = response.context_data['timetable']

        self.assertContains(response, 'Kendal - Barrow-in-Furness')

        self.assertEqual('2016-12-15', str(timetable.date))

        self.assertEqual(str(timetable.groupings[0].rows[0].times[:3]), '[05:20, 06:20, 07:15]')
        self.assertEqual(str(timetable.groupings[1].rows[0].times[:3]), '[07:00, 08:00, 09:00]')

        # Test abbreviations (check the colspan and rowspan attributes of Cells)
        self.assertEqual(timetable.groupings[1].rows[0].times[3].colspan, 6)
        # self.assertEqual(timetable.groupings[1].rows[0].times[3].rowspan, 104)
        self.assertFalse(timetable.groupings[1].rows[43].has_waittimes)
        # self.assertTrue(timetable.groupings[1].rows[44].has_waittimes)
        # self.assertFalse(timetable.groupings[1].rows[45].has_waittimes)
        self.assertEqual(str(timetable.groupings[0].rows[0].times[:6]), '[05:20, 06:20, 07:15, 08:10, 09:10, 10:10]'),

    @freeze_time('2017-08-29')
    def test_timetable_abbreviations_notes(self):
        """Test a timetable with a note which should determine the bounds of an abbreviation"""

        self.write_files_to_zipfile_and_import('EA.zip', ['set_5-28-A-y08.xml'])
        service = Service.objects.get()
        response = self.client.get(service.get_absolute_url())
        timetable = response.context_data['timetable']
        self.assertEqual('2017-08-29', str(timetable.date))

        self.assertEqual(str(timetable.groupings[0].rows[0].times[17]), 'then every 20 minutes until')
        # self.assertEqual(timetable.groupings[0].rows[11].times[15], time(9, 8))
        # self.assertEqual(timetable.groupings[0].rows[11].times[16], time(9, 34))
        # self.assertEqual(timetable.groupings[0].rows[11].times[17], time(15, 34))
        # self.assertEqual(timetable.groupings[0].rows[11].times[18], time(15, 54))
        feet = list(timetable.groupings[0].column_feet.values())[0]
        self.assertEqual(feet[0].span, 9)
        self.assertEqual(feet[1].span, 2)
        self.assertEqual(feet[2].span, 24)
        self.assertEqual(feet[3].span, 1)
        self.assertEqual(feet[4].span, 10)

        self.assertEqual(service.outbound_description, 'Basildon - South Benfleet - Southend On Sea via Hadleigh')
        self.assertEqual(service.inbound_description, 'Southend On Sea - South Benfleet - Basildon via Hadleigh')

    @freeze_time('2017-12-10')
    def test_timetable_derby_alvaston_circular(self):
        """Test a weird timetable where 'Wilmorton Ascot Drive' is visited twice consecutively on on one journey"""

        self.write_files_to_zipfile_and_import('EA.zip', ['em_11-1-J-y08-1.xml'])
        service = Service.objects.get()
        response = self.client.get(service.get_absolute_url())
        timetable = response.context_data['timetable']
        self.assertEqual('2017-12-10', str(timetable.date))

        self.assertEqual(60, len(timetable.groupings[0].rows))

    @freeze_time('2017-04-13')
    def test_timetable_deadruns(self):
        """Test a timetable with some dead runs which should be respected"""

        self.write_files_to_zipfile_and_import('NE.zip', ['SVRLABO024A.xml'])
        service = Service.objects.get()
        response = self.client.get(service.get_absolute_url())
        timetable = response.context_data['timetable']
        self.assertEqual('2017-04-13', str(timetable.date))

        self.assertEqual(len(timetable.groupings[0].rows), 49)
        self.assertEqual(len(timetable.groupings[1].rows), 29)

        self.assertEqual(str(timetable.groupings[0].rows[0].times), "[19:12, '', '']")
        self.assertEqual(str(timetable.groupings[0].rows[-25].times), '[19:32, 21:02, 22:32]')
        self.assertEqual(str(timetable.groupings[0].rows[-24].times), '[19:33, 21:03, 22:33]')
        self.assertEqual(str(timetable.groupings[0].rows[-12].times), '[19:42, 21:12, 22:42]')
        self.assertEqual(str(timetable.groupings[0].rows[-8].times), '[19:47, 21:17, 22:47]')
        self.assertEqual(str(timetable.groupings[0].rows[-7].times), '[19:48, 21:18, 22:48]')
        self.assertEqual(str(timetable.groupings[0].rows[-1].times), '[19:53, 21:23, 22:53]')

        self.assertEqual(str(timetable.groupings[1].rows[0].times), '[20:35, 22:05, 23:30]')
        self.assertEqual(str(timetable.groupings[1].rows[-25].times), '[20:38, 22:08, 23:33]')
        self.assertEqual(str(timetable.groupings[1].rows[-24].times), '[20:39, 22:09, 23:34]')
        self.assertEqual(str(timetable.groupings[1].rows[-12].times), '[20:52, 22:22, 23:47]')
        self.assertEqual(str(timetable.groupings[1].rows[-8].times), '[20:55, 22:25, 23:50]')
        self.assertEqual(str(timetable.groupings[1].rows[-7].times), '[20:55, 22:25, 23:50]')
        self.assertEqual(str(timetable.groupings[1].rows[-1].times), '[20:58, 22:28, 23:53]')

        self.assertEqual(str(timetable.groupings[0].rows[-3].stop), 'Eldon Street')
        self.assertEqual(str(timetable.groupings[0].rows[-2].stop), 'Railway Station')
        self.assertEqual(str(timetable.groupings[0].rows[-1].stop), 'Bus Station')
        self.assertEqual(str(timetable.groupings[1].rows[-3].stop), 'Twist Moor Lane')
        self.assertEqual(str(timetable.groupings[1].rows[-2].stop), 'Gladstone Terrace')
        self.assertEqual(str(timetable.groupings[1].rows[-1].stop), 'Hare and Hounds')

        response = self.client.get(service.get_absolute_url() + '?date=2017-04-16')
        timetable = response.context_data['timetable']
        self.assertEqual('2017-04-16', str(timetable.date))
        self.assertEqual(str(timetable.groupings[0].rows[0].times[2:]), '[15:28, 16:27, 17:28, 18:28, 19:28]')
        self.assertEqual(str(timetable.groupings[0].rows[-26].times[-1]), '19:50')
        self.assertEqual(str(timetable.groupings[0].rows[-25].times[-1]), '19:51')
        self.assertEqual(str(timetable.groupings[0].rows[-24].times[-1]), '')
        self.assertEqual(str(timetable.groupings[0].rows[-23].times[-1]), '')
        self.assertEqual(str(timetable.groupings[0].rows[-6].times[-1]), '')
        self.assertEqual(str(timetable.groupings[0].rows[-5].times[-1]), '')
        self.assertEqual(str(timetable.groupings[0].rows[-4].times[-1]), '')
        self.assertEqual(str(timetable.groupings[0].rows[-3].times[2:]), "[17:04, 18:05, 19:05, '']")
        self.assertEqual(str(timetable.groupings[0].rows[-2].times[2:]), "[17:04, 18:05, 19:05, '']")
        self.assertEqual(str(timetable.groupings[0].rows[-1].times[2:]), "[17:06, 18:07, 19:07, '']")

        # Several journeys a day on bank holidays
        # deadruns = txc.timetable_from_filename(FIXTURES_DIR, 'SVRLABO024A.xml', date(2017, 4, 14))
        # self.assertEqual(7, len(deadruns.groupings[0].rows[0].times))

    @freeze_time('2017-08-30')
    def test_timetable_servicedorg(self):
        """Test a timetable with a ServicedOrganisation"""

        self.write_files_to_zipfile_and_import('EA.zip', ['swe_34-95-A-y10.xml'])
        service = Service.objects.get()

        # Doesn't stop at Budehaven School during holidays
        response = self.client.get(service.get_absolute_url())
        self.assertEqual('2017-08-30', str(response.context_data['timetable'].date))
        self.assertNotContains(response, 'Budehaven School')

        # Does stop at Budehaven School twice a day on school days
        response = self.client.get(service.get_absolute_url() + '?date=2017-09-13')
        timetable = response.context_data['timetable']
        self.assertEqual('2017-09-13', str(timetable.date))
        self.assertContains(response, 'Budehaven School')
        # rows = timetable.groupings[1].rows
        # self.assertEqual(rows[-4].times, [time(8, 33, 10), '', '', '', time(15, 30, 10), ''])
        # self.assertEqual(rows[-5].times, [time(8, 33), '', '', '', time(15, 30), ''])
        # self.assertEqual(rows[-6].times, [time(8, 32, 18), '', '', '', time(15, 29, 18), ''])

    @freeze_time('2017-01-23')
    def test_timetable_holidays_only(self):
        """Test a service with a HolidaysOnly operating profile
        """
        self.write_files_to_zipfile_and_import('EA.zip', ['twm_6-14B-_-y11-1.xml'])
        service = Service.objects.get()

        self.assertNotIn('timetable', self.client.get(service.get_absolute_url()).context_data)
        # self.assertEqual(0, len(timetable.groupings[0].rows[0].times))
        # self.assertEqual(0, len(timetable.groupings[1].rows[0].times))

        # Has some journeys that operate on 1 May 2017
        # timetable = txc.timetable_from_filename(FIXTURES_DIR, 'twm_6-14B-_-y11-1.xml', date(2017, 5, 1))
        # self.assertEqual(8, len(timetable.groupings[0].rows[0].times))
        # self.assertEqual(8, len(timetable.groupings[1].rows[0].times))

    @freeze_time('2012-06-27')
    def test_timetable_goole(self):
        self.write_files_to_zipfile_and_import('W.zip', ['SVRYEAGT00.xml'])
        service = Service.objects.get()

        # try date outside of operating period
        response = self.client.get(service.get_absolute_url() + '?date=2007-06-27')
        timetable = response.context_data['timetable']
        # during a DaysOfNonOperation
        self.assertEqual('2012-06-27', str(timetable.date))
        self.assertEqual([], timetable.groupings)

        response = self.client.get(service.get_absolute_url() + '?date=2017-01-27')
        timetable = response.context_data['timetable']
        self.assertEqual('2017-01-27', str(timetable.date))
        self.assertEqual(str(timetable.groupings[0].rows[0].times),
                         "['', '', 09:48, 10:28, 11:08, 11:48, 12:28, 13:08, 13:48, 14:28, 15:08, '', '']")

        with freeze_time('21 Feb 2016'):  # Sunday
            date_options = list(timetable.date_options())
            self.assertEqual(date_options[0], date(2016, 2, 22))  # Monday
            self.assertEqual(date_options[-1], date(2017, 1, 27))

    @freeze_time('2017-01-01')
    def test_cardiff_airport(self):
        """Should be able to distinguish between Cardiff and Cardiff Airport as start and end of a route"""
        self.write_files_to_zipfile_and_import('W.zip', ['TCAT009.xml'])
        service = Service.objects.get()
        self.assertEqual(service.inbound_description, 'Cardiff  - Cardiff Airport')
        self.assertEqual(service.outbound_description, 'Cardiff Airport - Cardiff ')

    @freeze_time('2018-09-24')
    def test_timetable_plymouth(self):
        self.write_files_to_zipfile_and_import('EA.zip', ['20-plymouth-city-centre-plympton.xml'])
        service = Service.objects.get()
        response = self.client.get(service.get_absolute_url())
        timetable = response.context_data['timetable']

        self.assertEqual(str(timetable.groupings[1].rows[0].stop), "Plympton Mudge Way")
        # self.assertEqual(str(timetable.groupings[1].rows[1].stop), "Plympton St Mary's Bridge")
        self.assertEqual(str(timetable.groupings[1].rows[1].stop), "Underwood (Plymouth) Old Priory Junior School")
        # self.assertEqual(str(timetable.groupings[1].rows[2].stop), "Plympton Priory Junior School")
        self.assertEqual(str(timetable.groupings[1].rows[2].stop), "Plympton St Mary's Church")
        # self.assertEqual(str(timetable.groupings[1].rows[3].stop), "Plympton Dark Street Lane")
        self.assertEqual(str(timetable.groupings[1].rows[3].stop), "Plympton Colebrook Tunnel")
        self.assertEqual(str(timetable.groupings[1].rows[4].stop), "Plympton Glenside Surgey")
        self.assertFalse(timetable.groupings[1].rows[3].has_waittimes)
        # self.assertTrue(timetable.groupings[1].rows[4].has_waittimes)
        self.assertFalse(timetable.groupings[1].rows[5].has_waittimes)
        self.assertFalse(timetable.groupings[1].rows[6].has_waittimes)

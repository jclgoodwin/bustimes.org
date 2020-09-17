import os
import zipfile
import xml.etree.cElementTree as ET
import warnings
from tempfile import TemporaryDirectory
from datetime import date
from freezegun import freeze_time
from django.test import TestCase, override_settings
from django.utils import timezone
from django.core.management import call_command
from django.contrib.gis.geos import Point
from busstops.models import Region, StopPoint, Service, Operator, OperatorCode, DataSource, ServiceLink
from ...models import Route, Trip, Calendar, CalendarDate
from ..commands import import_transxchange


FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


@override_settings(
    TNDS_DIR=FIXTURES_DIR,
    FIRST_OPERATORS=()
)
class ImportTransXChangeTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ea = Region.objects.create(pk='EA', name='East Anglia')
        cls.w = Region.objects.create(pk='W', name='Wales')
        cls.gb = Region.objects.create(pk='GB', name='Großbritannien')
        cls.sc = Region.objects.create(pk='S', name='Scotland')
        Region.objects.bulk_create([
            Region(pk='NE', name='North East'),
            Region(pk='NW', name='North West'),
            Region(pk='IM', name='Isle of Man')
        ])

        cls.fecs = Operator.objects.create(pk='FECS', region_id='EA', name='First in Norfolk & Suffolk')
        Operator.objects.create(id='bus-vannin', region_id='EA', name='Bus Vannin')
        cls.megabus = Operator.objects.create(pk='MEGA', region_id='GB', name='Megabus')
        cls.fabd = Operator.objects.create(pk='FABD', region_id='S', name='First Aberdeen')

        nocs = DataSource.objects.create(name='National Operator Codes')
        OperatorCode.objects.create(operator=cls.megabus, source=nocs, code='MEGA')
        OperatorCode.objects.create(operator=cls.fabd, source=nocs, code='FABD')

        source = DataSource.objects.create(name='EA', url='https://www.example.co.uk/open-data')
        OperatorCode.objects.create(operator=cls.fecs, source=source, code='FECS')

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
                    ('2900A181', '', '', 0, 0),
            )
        )

    @staticmethod
    def handle_files(archive_name, filenames):
        command = import_transxchange.Command()
        command.service_descriptions = {}
        command.service_ids = set()
        command.route_ids = set()
        command.undefined_holidays = set()
        command.calendar_cache = {}
        command.corrections = {}
        command.open_data_operators = set()
        command.incomplete_operators = set()
        command.notes = {}

        command.set_region(archive_name)
        command.source.datetime = timezone.now()
        for filename in filenames:
            path = os.path.join(FIXTURES_DIR, filename)
            with open(path, 'r') as open_file:
                command.handle_file(open_file, filename)

    @classmethod
    def write_files_to_zipfile_and_import(cls, zipfile_name, filenames):
        with TemporaryDirectory() as directory:
            zipfile_path = os.path.join(directory, zipfile_name)
            with zipfile.ZipFile(zipfile_path, 'a') as open_zipfile:
                for filename in filenames:
                    cls.write_file_to_zipfile(open_zipfile, filename)
            call_command('import_transxchange', zipfile_path)

    @staticmethod
    def write_file_to_zipfile(open_zipfile, filename):
        open_zipfile.write(os.path.join(FIXTURES_DIR, filename), filename)

    @freeze_time('3 October 2016')
    def test_east_anglia(self):
        self.handle_files('EA.zip', ['ea_20-12-_-y08-1.xml', 'ea_21-13B-B-y08-1.xml'])

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
        self.assertEqual(8, CalendarDate.objects.count())

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
        # self.assertEqual(service.outbound_description, 'Norwich - Wymondham - Attleborough')
        # self.assertEqual(service.inbound_description, 'Attleborough - Wymondham - Norwich')
        self.assertEqual(service.operator.first(), self.fecs)
        self.assertEqual(
            list(service.get_traveline_links()),
            [('http://www.travelinesoutheast.org.uk/se/XSLT_TTB_REQUEST'
             '?line=2113B&lineVer=1&net=ea&project=y08&sup=B&command=direct&outputFormat=0',
                'Timetable on the Traveline website')]
        )

        res = self.client.get(service.get_absolute_url())
        self.assertEqual(res.context_data['breadcrumb'], [self.ea, self.fecs])
        self.assertContains(res, """
            <tr class="minor">
                <th><a href="/stops/2900N12345">Norwich Brunswick Road</a></th><td>19:48</td><td>22:56</td>
            </tr>
        """, html=True)
        self.assertContains(res, '<option selected value="2016-10-03">Monday 3 October 2016</option>')

        res = self.client.get(service.get_absolute_url())
        self.assertContains(res, '<option selected value="2016-10-03">Monday 3 October 2016</option>')
        self.assertContains(res, """
            <tr class="minor">
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

        self.assertContains(res, 'data from <a href="https://www.example.co.uk/open-data">EA</a>')

        # Test the fallback version without a timetable (just a list of stops)
        service.show_timetable = False
        service.save(update_fields=['show_timetable'])
        res = self.client.get(service.get_absolute_url())
        self.assertContains(res, """<li>
            <a href="/stops/2900A181"></a>
        </li>""")
        self.assertContains(res, 'Norwich - Wymondham - Attleborough')
        # self.assertContains(res, 'Attleborough - Wymondham - Norwich')

    @freeze_time('30 October 2017')
    def test_service_with_empty_pattern(self):
        self.handle_files('EA.zip', ['swe_33-9A-A-y10-2.xml'])

        route = Route.objects.get(line_name='9A')
        self.assertEqual('9A – Sidwell Street - Marine Place', str(route))

        res = self.client.get(route.service.get_absolute_url() + '?date=2016-12-28')
        timetable = res.context_data['timetable']
        self.assertEqual(75, len(timetable.groupings[0].rows))
        self.assertEqual(82, len(timetable.groupings[1].rows))

        self.assertEqual(157, route.service.stopusage_set.count())

    @freeze_time('23 January 2017')
    def test_do_service_wales(self):
        """Test a timetable from Wales (with SequenceNumbers on Journeys),
        with a university ServicedOrganisation
        """
        self.handle_files('W.zip', ['CGAO305.xml'])

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
        self.assertContains(response, '<li>Wednesday 12 April 2017–Tuesday 30 May 2017</li>')

        response = self.client.get(service.get_absolute_url() + '?date=2017-04-20')
        timetable = response.context_data['timetable']
        self.assertEqual('2017-04-20', str(timetable.date))
        self.assertEqual(1, len(timetable.groupings))
        self.assertEqual(3, len(timetable.groupings[0].rows[0].times))

        self.assertContains(
            response,
            'data from <a href="https://www.travelinedata.org.uk/">the Traveline National Dataset</a>'
        )

        self.assertEqual(19, service.stopusage_set.count())

    @freeze_time('2016-12-15')
    def test_timetable_ne(self):
        """Test timetable with some abbreviations"""
        self.handle_files('NE.zip', ['NE_03_SCC_X6_1.xml'])
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

        self.assertEqual(149, service.stopusage_set.order_by().distinct('stop_id').count())

    @freeze_time('2017-08-29')
    def test_timetable_abbreviations_notes(self):
        """Test a timetable with a note which should determine the bounds of an abbreviation"""

        self.handle_files('EA.zip', ['set_5-28-A-y08.xml'])
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

        self.assertEqual(138, service.stopusage_set.count())

    @freeze_time('2017-12-10')
    def test_timetable_derby_alvaston_circular(self):
        """Test a weird timetable where 'Wilmorton Ascot Drive' is visited twice consecutively on on one journey"""

        self.handle_files('EA.zip', ['em_11-1-J-y08-1.xml'])
        service = Service.objects.get()
        response = self.client.get(service.get_absolute_url())
        timetable = response.context_data['timetable']
        self.assertEqual('2017-12-10', str(timetable.date))

        self.assertEqual(60, len(timetable.groupings[0].rows))

    @freeze_time('2017-04-13')
    def test_timetable_deadruns(self):
        """Test a timetable with some dead runs which should be respected"""

        self.handle_files('NE.zip', ['SVRLABO024A.xml'])
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

        self.assertEqual(102, service.stopusage_set.count())

        # Several journeys a day on bank holidays
        # deadruns = txc.timetable_from_filename(FIXTURES_DIR, 'SVRLABO024A.xml', date(2017, 4, 14))
        # self.assertEqual(7, len(deadruns.groupings[0].rows[0].times))

    @freeze_time('2017-08-30')
    def test_timetable_servicedorg(self):
        """Test a timetable with a ServicedOrganisation"""

        self.handle_files('EA.zip', ['swe_34-95-A-y10.xml'])
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
        rows = timetable.groupings[1].rows
        self.assertEqual(str(rows[-4].times), "[08:33, '', '', '', 15:30, '']")
        self.assertEqual(str(rows[-5].times), "[08:33, '', '', '', 15:30, '']")
        self.assertEqual(str(rows[-6].times), "[08:32, '', '', '', 15:29, '']")

        self.assertEqual(114, service.stopusage_set.count())

    @freeze_time('2017-01-23')
    def test_timetable_holidays_only(self):
        """Test a service with a HolidaysOnly operating profile
        """
        self.handle_files('EA.zip', ['twm_6-14B-_-y11-1.xml'])
        service = Service.objects.get()

        response = self.client.get(service.get_absolute_url())
        self.assertNotIn('timetable', response.context_data)

        # Has some journeys that operate on 1 May 2017
        with freeze_time(date(2017, 4, 28)):
            response = self.client.get(service.get_absolute_url())
            timetable = response.context_data['timetable']
            self.assertEqual(timetable.date, date(2017, 5, 1))
            self.assertEqual(8, len(timetable.groupings[0].rows[0].times))
            self.assertEqual(8, len(timetable.groupings[1].rows[0].times))

        self.assertEqual(107, service.stopusage_set.count())

    @freeze_time('2012-06-27')
    def test_timetable_goole(self):
        self.handle_files('W.zip', ['SVRYEAGT00.xml'])
        service = Service.objects.get()

        # try date outside of operating period
        response = self.client.get(service.get_absolute_url() + '?date=2007-06-27')
        timetable = response.context_data['timetable']
        # next day of operation
        self.assertEqual('2012-06-30', str(timetable.date))
        self.assertEqual(1, len(timetable.groupings))
        self.assertEqual(str(timetable.groupings[0].rows[0].times),
                         "['', 09:08, 09:48, 10:28, 11:08, 11:48, 12:28, 13:08, 13:48, 14:28, 15:08, '', '']")

        response = self.client.get(service.get_absolute_url() + '?date=2017-01-27')
        timetable = response.context_data['timetable']
        self.assertEqual('2017-01-27', str(timetable.date))
        self.assertEqual(str(timetable.groupings[0].rows[0].times),
                         "['', '', 09:48, 10:28, 11:08, 11:48, 12:28, 13:08, 13:48, 14:28, 15:08, '', '']")

        with freeze_time('21 Feb 2016'):  # Sunday
            date_options = list(timetable.date_options())
            self.assertEqual(date_options[0], date(2016, 2, 22))  # Monday
            self.assertEqual(date_options[-1], date(2017, 1, 27))

        self.assertEqual(37, service.stopusage_set.count())

    @freeze_time('2017-01-01')
    def test_cardiff_airport(self):
        """Should be able to distinguish between Cardiff and Cardiff Airport as start and end of a route"""
        self.handle_files('W.zip', ['TCAT009.xml'])
        service = Service.objects.get()
        self.assertEqual(service.inbound_description, 'Cardiff  - Cardiff Airport')
        self.assertEqual(service.outbound_description, 'Cardiff Airport - Cardiff ')

        self.assertEqual(17, service.stopusage_set.count())

    @freeze_time('2018-09-24')
    def test_timetable_plymouth(self):
        self.handle_files('EA.zip', ['20-plymouth-city-centre-plympton.xml'])
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

        self.assertEqual(74, service.stopusage_set.count())

        route = service.route_set.get()

        response = self.client.get(service.get_absolute_url() + '/debug')
        self.assertContains(response, route.get_absolute_url())

        with self.assertRaises(FileNotFoundError):
            self.client.get(route.get_absolute_url())

    def test_multiple_operators(self):
        with freeze_time('2020-02-22'):
            self.write_files_to_zipfile_and_import('EA.zip', ['SVRABAO421.xml'])
        service = Service.objects.get()
        self.assertTrue(service.current)

        service.slug = 'abao421'
        service.save(update_fields=['slug'])

        self.assertEqual(service.slug, 'abao421')

        # after operating period
        with freeze_time('2022-02-22'):
            self.write_files_to_zipfile_and_import('EA.zip', ['SVRABAO421.xml'])
        service = Service.objects.get()
        self.assertFalse(service.current)
        self.assertEqual(service.slug, 'abao421')

        # back within operating period - should update slug
        with freeze_time('2020-02-22'):
            self.write_files_to_zipfile_and_import('EA.zip', ['SVRABAO421.xml'])
        service = Service.objects.get()
        self.assertTrue(service.current)
        self.assertEqual(service.slug, '421-inverurie-alford')

    def test_multiple_services(self):
        with freeze_time('2020-02-22'):
            self.handle_files('IOM.zip', ['Ser 16 16A 16B.xml'])
        services = Service.objects.filter(region='IM')
        self.assertEqual(3, len(services))

        self.assertEqual(1, Trip.objects.filter(route__service=services[0]).count())
        self.assertEqual(1, Trip.objects.filter(route__service=services[1]).count())
        self.assertEqual(2, Trip.objects.filter(route__service=services[2]).count())

    def test_service_error(self):
        """A file with some wrong references should be handled gracefully"""
        with self.assertLogs(level='ERROR'):
            self.handle_files('NW.zip', ['NW_05_PBT_6_1.xml'])

    def test_services_nw(self):
        self.handle_files('NW.zip', ['NW_04_GMN_2_1.xml', 'NW_04_GMS_237_1.xml', 'NW_04_GMS_237_2.xml'])

        # 2
        service = Service.objects.get(service_code='NW_04_GMN_2_1')
        self.assertEqual(service.description, 'intu Trafford Centre - Eccles - Swinton - Bolton')

        self.assertEqual(23, service.stopusage_set.all().count())

        # Stagecoach Manchester 237
        service = Service.objects.get(service_code='NW_04_GMS_237_1')
        duplicate = Service.objects.get(service_code='NW_04_GMS_237_2')
        ServiceLink.objects.create(from_service=service, to_service=duplicate, how='parallel')

        self.assertEqual(service.description, 'Glossop - Stalybridge - Ashton')

        service.geometry = 'SRID=4326;MULTILINESTRING((1.31326925542 51.1278853356,1.08276947772 51.2766792559))'
        service.save(update_fields=['geometry'])

        with freeze_time('1 September 2017'):
            with self.assertNumQueries(11):
                res = self.client.get(service.get_absolute_url() + '?date=2017-09-01')
        self.assertEqual(str(res.context_data['timetable'].date), '2017-09-01')
        self.assertContains(res, 'Timetable changes from Sunday 3 September 2017')
        self.assertContains(res, f'data-service="{service.id},{duplicate.id}"></div')

        with freeze_time('1 October 2017'):
            with self.assertNumQueries(15):
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
            with self.assertNumQueries(15):
                res = self.client.get(service.get_absolute_url() + '?date=2017-10-03')
        self.assertContains(res, """
                <thead>
                    <tr>
                        <td></td>
                        <td colspan="27">
                            <a href="/services/237-glossop-stalybridge-ashton-2">237</a>
                        </td>
                    </tr>
                </thead>
        """, html=True)
        self.assertEqual(str(res.context_data['timetable'].date), '2017-10-03')
        self.assertEqual(27, len(res.context_data['timetable'].groupings[0].trips))
        self.assertEqual(30, len(res.context_data['timetable'].groupings[1].trips))

        self.assertEqual(87, service.stopusage_set.all().count())
        # self.assertEqual(121, duplicate.stopusage_set.all().count())

    @freeze_time('25 June 2016')
    def test_do_service_scotland(self):
        # simulate a Scotland zipfile:
        self.handle_files('S.zip', ['SVRABBN017.xml'])

        service = Service.objects.get(service_code='ABBN017')

        self.assertEqual(str(service), 'N17 - Aberdeen - Dyce')
        self.assertTrue(service.show_timetable)
        self.assertEqual(service.operator.first(), self.fabd)
        self.assertEqual(
            list(service.get_traveline_links()),
            [('http://www.travelinescotland.com/lts/#/timetables?'
             'timetableId=ABBN017&direction=OUTBOUND&queryDate=&queryTime=',
                'Timetable on the Traveline Scotland website')]
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

        self.assertEqual(88, service.stopusage_set.count())

    @freeze_time('22 January 2017')
    def test_megabus(self):
        # simulate a National Coach Service Database zip file
        with TemporaryDirectory() as directory:
            zipfile_path = os.path.join(directory, 'NCSD.zip')
            with zipfile.ZipFile(zipfile_path, 'a') as open_zipfile:
                self.write_file_to_zipfile(open_zipfile, os.path.join('NCSD_TXC',
                                           'Megabus_Megabus14032016 163144_MEGA_M11A.xml'))
                self.write_file_to_zipfile(open_zipfile, os.path.join('NCSD_TXC',
                                           'Megabus_Megabus14032016 163144_MEGA_M12.xml'))
                self.write_file_to_zipfile(open_zipfile, 'IncludedServices.csv')
            call_command('import_transxchange', zipfile_path)
            # test re-importing a previously imported service again
            call_command('import_transxchange', zipfile_path)

        # M11A

        res = self.client.get('/services/m11a-belgravia-liverpool?date=ceci n\'est pas une date')

        service = res.context_data['object']

        self.assertEqual(str(service), 'M11A - Belgravia - Liverpool')
        self.assertTrue(service.show_timetable)
        self.assertEqual(service.operator.first(), self.megabus)
        self.assertEqual(
            list(service.get_traveline_links()),
            [('http://www.travelinesoutheast.org.uk/se/XSLT_TTB_REQUEST'
             '?line=11M11&sup=A&net=nrc&project=y08&command=direct&outputFormat=0',
                'Timetable on the Traveline website')]
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
        self.assertContains(res, '/js/timetable.')

        timetable = res.context_data['timetable']
        self.assertFalse(timetable.groupings[0].has_minor_stops())
        self.assertFalse(timetable.groupings[1].has_minor_stops())
        self.assertEqual(str(timetable.groupings[1].rows[0].times), '[13:00, 15:00, 16:00, 16:30, 18:00, 20:00, 23:45]')

        # should only be 6, despite running 'import_services' twice
        self.assertEqual(6, service.stopusage_set.count())

        # M12

        service = Service.objects.get(service_code='M12_MEGA')

        with freeze_time('1 January 2017'):
            res = self.client.get(service.get_absolute_url())

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
        command = import_transxchange.Command()
        command.set_region('EA.zip')
        element = ET.fromstring("""
            <txc:Operator xmlns:txc="http://www.transxchange.org.uk/" id="OId_RRS">
                <txc:OperatorCode>RRS</txc:OperatorCode>
                <txc:OperatorShortName>Replacement Service</txc:OperatorShortName>
                <txc:OperatorNameOnLicence>Replacement Service</txc:OperatorNameOnLicence>
                <txc:TradingName>Replacement Service</txc:TradingName>
            </txc:Operator>
        """)
        self.assertIsNone(command.get_operator(element))

        with warnings.catch_warnings(record=True) as caught_warnings:
            self.assertIsNone(command.get_operator(ET.fromstring("""
                <txc:Operator xmlns:txc="http://www.transxchange.org.uk/" id="OId_RRS">
                    <txc:OperatorCode>BEAN</txc:OperatorCode>
                    <txc:TradingName>Bakers</txc:TradingName>
                </txc:Operator>
            """)))
            self.assertTrue('Operator not found:' in str(caught_warnings[0].message))

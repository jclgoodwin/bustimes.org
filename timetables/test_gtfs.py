import os
import zipfile
import vcr
from freezegun import freeze_time
from datetime import date
from django.test import TestCase, override_settings
from django.conf import settings
from django.core.management import call_command
from busstops.models import Region, AdminArea, StopPoint, Service, Operator


FIXTURES_DIR = os.path.join(settings.BASE_DIR, 'busstops', 'management', 'tests', 'fixtures')


@override_settings(DATA_DIR=FIXTURES_DIR, IE_COLLECTIONS=['mortons', 'seamusdoherty'])
@freeze_time('2019-08-30')
class GTFSTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        """Make a GTFS feed (a zip file containing some text files)."""

        cls.leinster = Region.objects.create(
            id='LE',
            name='Leinster'
        )
        cls.ulster = Region.objects.create(
            id='UL',
            name='Ulster'
        )
        cls.dublin = AdminArea.objects.create(
            id=822,
            atco_code=822,
            region_id='LE',
            name='Dublin'
        )
        cls.south_dublin = AdminArea.objects.create(
            id=823,
            atco_code=823,
            region_id='LE'
        )
        cls.donegal = AdminArea.objects.create(
            id=853,
            atco_code=853,
            region_id='UL'
        )

        # Create an existing operator (with a slightly different name) to test that it is re-used
        Operator.objects.create(id=132, name='Seumas Doherty', region=cls.leinster)

        for collection in settings.IE_COLLECTIONS:
            dir_path = os.path.join(FIXTURES_DIR, 'google_transit_' + collection)
            feed_path = dir_path + '.zip'
            with zipfile.ZipFile(feed_path, 'a') as open_zipfile:
                for item in os.listdir(dir_path):
                    open_zipfile.write(os.path.join(dir_path, item), item)

        with vcr.use_cassette(os.path.join(FIXTURES_DIR, 'google_transit_ie') + '.yaml'):
            call_command('import_ie_gtfs', '--force', '-v2')
        with vcr.use_cassette(os.path.join(FIXTURES_DIR, 'google_transit_ie') + '.yaml'):
            # import a second time - test that it's OK if stuff already exists
            call_command('import_ie_gtfs', '--force')

        for collection in settings.IE_COLLECTIONS:
            dir_path = os.path.join(FIXTURES_DIR, 'google_transit_' + collection)
            os.remove(dir_path + '.zip')

    def test_stops(self):
        stops = StopPoint.objects.all()
        self.assertEqual(len(stops), 75)
        stop = StopPoint.objects.get(atco_code='822000153')
        self.assertEqual(stop.common_name, 'Terenure Library')
        self.assertEqual(stop.admin_area_id, 822)

    def test_operator(self):
        self.assertEqual(Operator.objects.count(), 2)

    def test_small_timetable(self):
        with freeze_time('2017-06-07'):
            response = self.client.get('/services/165-merrion-citywest')
        timetable = response.context_data['timetable']
        self.assertEqual(str(timetable.groupings[0]), 'Merrion - Citywest')
        self.assertEqual(str(timetable.groupings[1]), 'Citywest - Ballsbridge')
        self.assertEqual(str(timetable.groupings[0].rows[0].times), '[07:45]')
        self.assertEqual(str(timetable.groupings[0].rows[4].times), '[07:52]')
        self.assertEqual(str(timetable.groupings[0].rows[6].times), '[08:01]')
        self.assertEqual(str(timetable.groupings[1].rows[0].times), '[17:20]')
        self.assertEqual(str(timetable.groupings[1].rows[6].times), '[17:45]')
        self.assertEqual(str(timetable.groupings[1].rows[-1].times), '[18:25]')
        self.assertEqual(len(timetable.groupings[0].rows), 18)
        self.assertEqual(len(timetable.groupings[1].rows), 14)

        for day in (date(2017, 6, 11), date(2017, 12, 25), date(2015, 12, 3), date(2020, 12, 3)):
            with freeze_time(day):
                response = self.client.get('/services/165-merrion-citywest')
                timetable = response.context_data['timetable']
                self.assertEqual(timetable.groupings, [])

    def test_big_timetable(self):
        service = Service.objects.get(service_code='seamusdoherty-963-1')
        timetable = service.get_timetable(date(2017, 6, 7))
        self.assertEqual(str(timetable.groupings[0].rows[0].times), "['', 10:15, '', 14:15, 17:45]")
        self.assertEqual(str(timetable.groupings[0].rows[1].times), "['', 10:20, '', 14:20, 17:50]")
        self.assertEqual(str(timetable.groupings[0].rows[2].times), "['', 10:22, '', 14:22, 17:52]")

    def test_admin_area(self):
        res = self.client.get(self.dublin.get_absolute_url())
        self.assertContains(res, 'Bus services in Dublin', html=True)
        self.assertContains(res, '/services/165')

import os
import zipfile
import vcr
from datetime import date, time
from django.test import TestCase, override_settings
from django.conf import settings
from django.core.management import call_command
from busstops.models import Region, AdminArea, StopPoint, Service, Operator


FIXTURES_DIR = os.path.join(settings.BASE_DIR, 'busstops', 'management', 'tests', 'fixtures')


@override_settings(DATA_DIR=FIXTURES_DIR, IE_COLLECTIONS=['mortons', 'seamusdoherty'])
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
        service = Service.objects.get(service_code='mortons-165')
        timetable = service.get_timetables(date(2017, 6, 7))[0]
        timetable.groupings.sort(key=lambda g: str(g), reverse=True)
        self.assertEqual(str(timetable.groupings[0]), 'Merrion - Citywest')
        self.assertEqual(str(timetable.groupings[1]), 'Citywest - Ballsbridge')
        self.assertEqual(timetable.groupings[0].rows[0].times, [time(7, 45)])
        self.assertEqual(timetable.groupings[0].rows[4].times, [time(7, 52)])
        self.assertEqual(timetable.groupings[0].rows[6].times, [time(8, 1)])
        self.assertEqual(timetable.groupings[1].rows[0].times, [time(17, 20)])
        self.assertEqual(timetable.groupings[1].rows[6].times, [time(17, 45)])
        self.assertEqual(timetable.groupings[1].rows[-1].times, [time(18, 25)])
        self.assertEqual(len(timetable.groupings[0].rows), 18)
        self.assertEqual(len(timetable.groupings[1].rows), 14)

        for day in (date(2017, 6, 11), date(2017, 12, 25), date(2015, 12, 3), date(2020, 12, 3)):
            timetable = service.get_timetables(day)[0]
            self.assertEqual(timetable.groupings, [])

    def test_big_timetable(self):
        service = Service.objects.get(service_code='seamusdoherty-963-1')
        timetable = service.get_timetables(date(2017, 6, 7))[0]
        self.assertEqual(timetable.groupings[0].rows[0].times,
                         ['     ', time(10, 15), '     ', time(14, 15), time(17, 45)])
        self.assertEqual(timetable.groupings[0].rows[1].times,
                         ['     ', time(10, 20), '     ', time(14, 20), time(17, 50)])
        self.assertEqual(timetable.groupings[0].rows[2].times,
                         ['     ', time(10, 22), '     ', time(14, 22), time(17, 52)])

    def test_admin_area(self):
        res = self.client.get(self.dublin.get_absolute_url())
        self.assertContains(res, 'Bus services in Dublin', html=True)
        self.assertContains(res, '/services/165')

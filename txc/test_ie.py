import os
import zipfile
from datetime import date, time
from django.test import TestCase, override_settings
from . import ie


FIXTURES_DIR = './busstops/management/tests/fixtures/'


class IrelandTest(TestCase):
    """Tests some timetables generated directly from XML files"""

    def setUp(self):
        self.dir_path = os.path.join(FIXTURES_DIR, 'google_transit_mortons')
        with zipfile.ZipFile(self.dir_path + '.zip', 'a') as open_zipfile:
            for item in os.listdir(self.dir_path):
                open_zipfile.write(os.path.join(self.dir_path, item), item)

    def tearDown(self):
        os.remove(self.dir_path + '.zip')

    @override_settings(DATA_DIR=FIXTURES_DIR)
    def test_small_timetable(self):
        timetable = ie.get_timetable('mortons-20-165-y11', date(2017, 6, 7))[0]
        self.assertEqual(str(timetable.groupings[0]), 'Merrion, Merlyn Park - Citywest, Castle House')
        self.assertEqual(str(timetable.groupings[1]), 'Citywest, Castle House - Ballsbridge, Ailesbury Road')
        self.assertEqual(timetable.groupings[0].rows[0].times, [time(7, 45)])
        self.assertEqual(timetable.groupings[0].rows[4].times, [time(7, 52)])
        self.assertEqual(timetable.groupings[0].rows[6].times, [time(8, 1)])
        self.assertEqual(timetable.groupings[1].rows[0].times, [time(17, 20)])
        self.assertEqual(timetable.groupings[1].rows[6].times, [time(17, 45)])
        self.assertEqual(timetable.groupings[1].rows[-1].times, [time(18, 25)])
        self.assertEqual(len(timetable.groupings[0].rows), 18)
        self.assertEqual(len(timetable.groupings[1].rows), 14)

        for day in (date(2017, 6, 11), date(2017, 12, 25), date(2015, 12, 3)):
            timetable = ie.get_timetable('mortons-20-165-y11', day)[0]
            self.assertEqual(timetable.groupings, [])
        with self.assertRaises(IOError) as context_manager:
            ie.get_timetable('dublincoac-', None)
        self.assertEqual(context_manager.exception.filename,
                         './busstops/management/tests/fixtures/google_transit_dublincoach.zip')

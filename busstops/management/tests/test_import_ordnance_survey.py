import os
import zipfile
from django.test import TestCase, override_settings
from django.core.management import call_command
from ...models import Place


FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


class ImportOrdnanceSurveyTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # create zip file
        zipfile_path = os.path.join(FIXTURES_DIR, 'opname_csv_gb.zip')

        with zipfile.ZipFile(zipfile_path, 'a') as open_zipfile:
            open_zipfile.write(os.path.join(FIXTURES_DIR, 'OS_Open_Names_Header.csv'),
                               os.path.join('DOC', 'OS_Open_Names_Header.csv'))
            open_zipfile.write(os.path.join(FIXTURES_DIR, 'OS_Open_Names.csv'),
                               os.path.join('DATA', 'OS_Open_Names.csv'))

        # import
        with override_settings(DATA_DIR=FIXTURES_DIR):
            call_command('import_ordnance_survey')

        # delete zip file
        os.remove(zipfile_path)

    def test_place(self):
        place = Place.objects.get(name='East Whitwell')
        self.assertEqual(str(place), 'East Whitwell')
        self.assertAlmostEqual(place.latlong.x, -1.5989521030895975)
        self.assertAlmostEqual(place.latlong.y, 53.47550914454518)
        self.assertAlmostEqual(place.polygon.centroid.x, -1.5996910109409872)

        res = self.client.get(place.get_absolute_url())
        self.assertContains(res, 'East Whitwell')

    def test_welsh_place(self):
        place = Place.objects.get(name='Beguildy')
        self.assertEqual(str(place), 'Beguildy')

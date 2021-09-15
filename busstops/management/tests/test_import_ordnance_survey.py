import os
import zipfile
from unittest.mock import patch
from tempfile import TemporaryDirectory
from django.test import TestCase, override_settings
from django.core.management import call_command
from ...models import Place


FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


class ImportOrdnanceSurveyTest(TestCase):
    def test_ordanance_survey_places(self):
        # create zip file
        with TemporaryDirectory() as directory:
            zipfile_path = os.path.join(directory, 'opname_csv_gb.zip')

            with zipfile.ZipFile(zipfile_path, 'a') as open_zipfile:
                open_zipfile.write(os.path.join(FIXTURES_DIR, 'OS_Open_Names_Header.csv'),
                                   os.path.join('DOC', 'OS_Open_Names_Header.csv'))
                open_zipfile.write(os.path.join(FIXTURES_DIR, 'OS_Open_Names.csv'),
                                   os.path.join('DATA', 'OS_Open_Names.csv'))

            # import
            with override_settings(DATA_DIR=directory):
                with patch('builtins.print') as mocked_print:
                    call_command('import_ordnance_survey')

        mocked_print.assert_called_with('Hamlet', 'Bugeildy')

        # East Whitwell:

        place = Place.objects.get(name='East Whitwell')
        self.assertEqual(str(place), 'East Whitwell')
        self.assertAlmostEqual(place.latlong.x, -1.5989521030895975)
        self.assertAlmostEqual(place.latlong.y, 53.47550914454518)
        self.assertAlmostEqual(place.polygon.centroid.x, -1.5996910109409872)

        res = self.client.get(place.get_absolute_url())
        self.assertContains(res, 'East Whitwell')

        # Beguildy:

        place = Place.objects.get(name='Beguildy')
        self.assertEqual(str(place), 'Beguildy')

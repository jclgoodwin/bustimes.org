import os
import zipfile
from django.test import TestCase, override_settings
from django.core.management import call_command
from ...models import Region, Service


FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


class ImportAccessibilityTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Region.objects.create(id='S')
        cls.service = Service.objects.create(service_code='HIAO915', date='2017-05-05', region_id='S')

        # create zip file
        zipfile_path = os.path.join(FIXTURES_DIR, 'accessibility-data.zip')
        filename = 'IF145_ModeAccessibility_v2_20170522_1802.csv'
        with zipfile.ZipFile(zipfile_path, 'a') as open_zipfile:
            open_zipfile.write(os.path.join(FIXTURES_DIR, filename), filename)

        # import
        with override_settings(DATA_DIR=FIXTURES_DIR):
            call_command('import_accessibility')

        # delete zip file
        os.remove(zipfile_path)

    def test_scotch_service(self):
        self.assertIsNone(self.service.wheelchair)
        self.assertIsNone(self.service.low_floor)
        self.assertIsNone(self.service.assistance_service)

        self.service.refresh_from_db()

        self.assertTrue(self.service.wheelchair)
        self.assertFalse(self.service.low_floor)
        self.assertFalse(self.service.assistance_service)

        response = self.client.get(self.service.get_absolute_url())
        self.assertContains(response, 'Not operated by low-floor buses')

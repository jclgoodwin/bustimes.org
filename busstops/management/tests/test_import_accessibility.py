import os
import zipfile
from django.test import TestCase, override_settings
from django.core.management import call_command
from ...models import Region, Service


FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


class ImportAccessibilityTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        for region_id, service_code in (
            ('S', 'HIAO915'), ('EA', 'ea_21-10-_-y08'), ('NW', 'NW_06_2288_672_1')
        ):
            Region.objects.create(id=region_id)
            Service.objects.create(service_code=service_code, date='2017-05-05', region_id=region_id)

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
        "Och aye the noo"
        service = Service.objects.get(region_id='S')

        self.assertTrue(service.wheelchair)
        self.assertFalse(service.low_floor)
        self.assertFalse(service.assistance_service)

        response = self.client.get(service.get_absolute_url())
        self.assertContains(response, 'Not operated by low-floor buses')
        self.assertContains(response, 'Wheelchair-accessible')
        self.assertNotContains(response, 'An assistance service')

    def test_norfolk_service(self):
        "Huge roof on my home"
        service = Service.objects.get(region_id='EA')

        response = self.client.get(service.get_absolute_url())

        self.assertContains(response, 'Operated by low-floor buses')
        self.assertContains(response, 'Wheelchair-accessible')
        self.assertContains(response, 'An assistance service')

    def test_north_west_service(self):
        service = Service.objects.get(region_id='NW')

        response = self.client.get(service.get_absolute_url())

        self.assertNotContains(response, 'low-floor buses')
        self.assertContains(response, 'Wheelchair-accessible')
        self.assertNotContains(response, 'An assistance service')

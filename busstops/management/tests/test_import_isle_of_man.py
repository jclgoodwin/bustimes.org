import os
import vcr
from django.test import TestCase, override_settings
from django.core.management import call_command
from ...models import StopPoint


FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


class ImportIsleOfManTest(TestCase):
    @classmethod
    def setUpTestData(cls, _):
        with override_settings(DATA_DIR=FIXTURES_DIR):
            with vcr.use_cassette(os.path.join(FIXTURES_DIR, 'isleofmanstops.yaml')):
                call_command('import_isle_of_man')

    def test_import_stops(self):
        self.assertEqual(833, StopPoint.objects.all().count())

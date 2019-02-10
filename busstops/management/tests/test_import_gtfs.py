import os
import vcr
from django.test import TestCase, override_settings
from django.core.management import call_command
from multigtfs.models import Feed
from ..commands import import_gtfs


FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


@override_settings(DATA_DIR=FIXTURES_DIR)
class ImportGTFSTest(TestCase):
    def test_download_if_modified(self):
        path = 'download_if_modified.txt'
        url = 'https://bustimes.org.uk/static/js/global.js'

        self.assertFalse(os.path.exists(path))

        with vcr.use_cassette('data/vcr/download_if_modified.yaml'):
            self.assertTrue(import_gtfs.download_if_modified(path, url))
            self.assertFalse(import_gtfs.download_if_modified(path, url))

        self.assertTrue(os.path.exists(path))

        os.remove(path)

    def test_handle(self):
        with vcr.use_cassette('data/vcr/import_gtfs.yaml'):
            with override_settings(TFWM={'app_id': 'Mark', 'app_key': 'Mardell'}):
                call_command('import_gtfs')
        self.assertFalse(Feed.objects.all())

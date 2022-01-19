"""Tests for importing NaPTAN data
"""
import vcr
from pathlib import Path
from tempfile import TemporaryDirectory
from django.core.management import call_command
from django.test import TestCase, override_settings
from ...models import StopPoint, DataSource


FIXTURES_DIR = Path(__file__).resolve().parent / 'fixtures'


class NaptanTest(TestCase):
    def test_download(self):
        with TemporaryDirectory() as temp_dir:
            with vcr.use_cassette(str(FIXTURES_DIR / 'naptan.yml')) as cassette:

                temp_dir_path = Path(temp_dir)

                with override_settings(DATA_DIR=temp_dir_path):

                    self.assertFalse((temp_dir_path / 'naptan.xml').exists())

                    call_command('naptan_new')

                    self.assertTrue((temp_dir_path / 'naptan.xml').exists())

                    source = DataSource.objects.get(name='NaPTAN')
                    self.assertEqual(source.settings[0]['LastUpload'], '03/09/2020')

                    cassette.rewind()

                    call_command('naptan_new')

                    source.settings[0]['LastUpload'] = '01/09/2020'
                    source.save(update_fields=['settings'])

                    cassette.rewind()

                    call_command('naptan_new')

        source.refresh_from_db()
        self.assertEqual(source.settings[0]['LastUpload'], '03/09/2020')

        stop = StopPoint.objects.get()
        self.assertEqual(str(stop), "Wroxham  ↑")
        self.assertEqual(stop.get_qualified_name(), "Wroxham")

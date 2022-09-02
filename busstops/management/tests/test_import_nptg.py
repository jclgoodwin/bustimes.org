from pathlib import Path
from tempfile import TemporaryDirectory

import vcr
from django.core.management import call_command
from django.test import TestCase, override_settings

from ...models import DataSource  # , AdminArea, Locality, Region, StopPoint


class ImportNPTGTest(TestCase):
    def test_nptg(self):
        fixtures_dir = Path(__file__).resolve().parent / "fixtures"

        with TemporaryDirectory() as temp_dir:
            with vcr.use_cassette(
                str(fixtures_dir / "nptg.yml"), decode_compressed_response=True
            ) as cassette:

                temp_dir_path = Path(temp_dir)

                with override_settings(DATA_DIR=temp_dir_path):

                    self.assertFalse((temp_dir_path / "nptg.xml").exists())

                    with self.assertNumQueries(621):
                        call_command("nptg_new")

                    source = DataSource.objects.get(name="NPTG")
                    self.assertEqual(str(source.datetime), "2022-08-29 18:57:00+00:00")

                    self.assertTrue((temp_dir_path / "nptg.xml").exists())

                    cassette.rewind()

                    with self.assertNumQueries(4):
                        call_command("nptg_new")

                    cassette.rewind()

                    with self.assertNumQueries(4):
                        call_command("nptg_new")

                    source = DataSource.objects.get(name="NPTG")
                    self.assertEqual(str(source.datetime), "2022-08-29 18:57:00+00:00")

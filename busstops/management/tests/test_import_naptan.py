"""Tests for importing NaPTAN data
"""
import vcr
from pathlib import Path
from tempfile import TemporaryDirectory
from django.core.management import call_command
from django.test import TestCase, override_settings
from ...models import Region, AdminArea, Locality, StopPoint, DataSource


FIXTURES_DIR = Path(__file__).resolve().parent / 'fixtures'


class NaptanTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Region.objects.create(id="EA", name="East Anglia")
        AdminArea.objects.create(id=91, atco_code="290", name="Norfolk", region_id="EA")
        AdminArea.objects.create(id=110, atco_code="910", name="National - National Rail", region_id="EA")
        Locality.objects.create(id='E0017763', name="Old Catton", admin_area_id=91)
        Locality.objects.create(id='E0017806', name="Berney Arms", admin_area_id=91)

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

        # inactive stop in Wroxham
        stop = StopPoint.objects.get(atco_code="2900FLEX1")
        self.assertEqual(str(stop), "Wroxham  ↑")
        self.assertEqual(stop.get_qualified_name(), "Wroxham")

        response = self.client.get("/stops/2900FLEX1")
        self.assertContains(response, " no services currently stop ", status_code=404)

        # active stop
        response = self.client.get("/stops/2900C1323")
        self.assertContains(response, '<li title="NaPTAN code">NFOAJGDT</li>')
        self.assertContains(response, '<p>On White Woman Lane, near Longe Lane</p>')

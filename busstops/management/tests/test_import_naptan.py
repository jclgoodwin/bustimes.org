"""Tests for importing NaPTAN data
"""
import vcr
from pathlib import Path
from tempfile import TemporaryDirectory
from django.core.management import call_command
from django.test import TestCase, override_settings
from ...models import Region, AdminArea, Locality, StopPoint, DataSource


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


class NaptanTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Region.objects.create(id="EA", name="East Anglia")
        AdminArea.objects.create(id=91, atco_code="290", name="Norfolk", region_id="EA")
        AdminArea.objects.create(
            id=110, atco_code="910", name="National - National Rail", region_id="EA"
        )
        AdminArea.objects.create(
            id=15, atco_code="076", name="Darlington", region_id="EA"
        )
        AdminArea.objects.create(
            id=90, atco_code="280", name="Merseyside", region_id="EA"
        )
        AdminArea.objects.create(
            id=92, atco_code="320", name="North Yorkshire", region_id="EA"
        )
        Locality.objects.create(id="E0017763", name="Old Catton", admin_area_id=91)
        Locality.objects.create(id="E0017806", name="Berney Arms", admin_area_id=91)
        Locality.objects.create(id="N0078629", name="Neasham Road", admin_area_id=15)
        Locality.objects.create(id="E0048995", name="Great Ayton", admin_area_id=92)
        StopPoint.objects.create(atco_code="07605395", active=True)

    def test_download(self):
        with TemporaryDirectory() as temp_dir:
            with vcr.use_cassette(str(FIXTURES_DIR / "naptan.yml")) as cassette:

                temp_dir_path = Path(temp_dir)

                with override_settings(DATA_DIR=temp_dir_path):

                    self.assertFalse((temp_dir_path / "naptan.xml").exists())

                    call_command("naptan_new")

                    self.assertTrue((temp_dir_path / "naptan.xml").exists())

                    source = DataSource.objects.get(name="NaPTAN")
                    self.assertEqual(source.settings[0]["LastUpload"], "03/09/2020")

                    cassette.rewind()

                    call_command("naptan_new")

                    source.settings[0]["LastUpload"] = "01/09/2020"
                    source.save(update_fields=["settings"])

                    cassette.rewind()

                    call_command("naptan_new")

        source.refresh_from_db()
        self.assertEqual(source.settings[0]["LastUpload"], "03/09/2020")

        # inactive stop in Wroxham
        stop = StopPoint.objects.get(atco_code="2900FLEX1")
        self.assertEqual(str(stop), "Wroxham  ↑")
        self.assertEqual(stop.get_qualified_name(), "Wroxham")

        response = self.client.get("/stops/2900flEx1")  # case insensitivity
        self.assertContains(response, " no services currently stop ", status_code=404)

        # active stop
        response = self.client.get("/stops/2900C1323")
        self.assertContains(response, '<li title="NaPTAN code">NFOAJGDT</li>')
        self.assertContains(response, "<p>On White Woman Lane, near Longe Lane</p>")

        # stop in area
        response = self.client.get("/stops/07605395")
        self.assertContains(response, "Neasham Road Brankin Drive (O)")
        self.assertContains(response, "On Brankin Road, near Brankin Drive")
        self.assertContains(response, "Darlington")
        stop = response.context_data["object"]
        self.assertEqual(stop.admin_area.name, "Darlington")
        self.assertEqual(stop.stop_area_id, "077G5394")
        self.assertEqual(stop.latlong.coords, (-1.538062647801621, 54.511514214023784))

        stop = StopPoint.objects.get(atco_code="3200GTAYTON0")
        self.assertEqual(stop.latlong.coords, (-1.117418697321657, 54.48934185786758))
        self.assertEqual(str(stop), "Great Ayton Rail Station (entrance)")

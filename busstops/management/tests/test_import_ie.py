"""Tests for importing Ireland stops and gazetteer"""

from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from ...models import AdminArea, Locality, Region, StopPoint, DataSource


class ImportIrelandTest(TestCase):
    """Test the NaPTAN and NPTG importers using Irish data"""

    def test_ie_nptg_and_naptan(self):
        fixtures_dir = Path(__file__).resolve().parent / "fixtures"
        DataSource.objects.create(name="ie_naptan")

        # NPTG (places):

        call_command("nptg_new", fixtures_dir / "ie_nptg.xml")

        regions = Region.objects.order_by("name")
        self.assertEqual(len(regions), 5)
        self.assertEqual(regions[0].name, "Connaught")
        self.assertEqual(regions[2].name, "Munster")

        areas = AdminArea.objects.order_by("name")
        self.assertEqual(len(areas), 40)

        self.assertEqual(areas[0].name, "Antrim")
        self.assertEqual(areas[0].region.name, "Ulster_NI")

        self.assertEqual(areas[2].name, "Carlow")
        self.assertEqual(areas[2].region.name, "Leinster")

        self.assertEqual(Locality.objects.count(), 5)

        dangan = Locality.objects.get(name="Dangan")
        self.assertEqual(dangan.admin_area.name, "Galway City")
        self.assertAlmostEqual(dangan.latlong.x, -9.077645)
        self.assertAlmostEqual(dangan.latlong.y, 53.290138)

        salthill = Locality.objects.get(name="Salthill")
        self.assertEqual(salthill.name, "Salthill")
        self.assertEqual(salthill.admin_area.name, "Galway City")
        self.assertAlmostEqual(salthill.latlong.x, -9.070427)
        self.assertAlmostEqual(salthill.latlong.y, 53.262565)

        # NaPTAN (stops):

        DataSource.objects.create(name="Irish NaPTAN")

        with override_settings(DATA_DIR=fixtures_dir), patch(
            "busstops.management.commands.naptan_new.download_if_modified",
            return_value=(True, None),
        ):
            call_command("naptan_new", "ie_naptan")

        stops = StopPoint.objects.order_by("atco_code")
        self.assertEqual(len(stops), 6)
        self.assertEqual(stops[0].atco_code, "700000004096")
        self.assertEqual(stops[0].common_name, "Rathfriland")
        self.assertEqual(stops[0].stop_type, "")
        self.assertEqual(stops[0].bus_stop_type, "")
        self.assertEqual(stops[0].timing_status, "")
        self.assertAlmostEqual(stops[0].latlong.x, -6.15849970528097)
        self.assertAlmostEqual(stops[0].latlong.y, 54.236552528081)

        stop = stops.get(atco_code="700000015422")
        self.assertEqual(stop.common_name, "Europa Buscentre Belfast")
        self.assertEqual(stop.street, "Glengall Street")
        self.assertEqual(stop.crossing, "")
        self.assertEqual(stop.indicator, "In")
        self.assertEqual(stop.bearing, "")
        self.assertEqual(stop.timing_status, "OTH")
        self.assertAlmostEqual(stop.latlong.x, -5.93626793184173)
        self.assertAlmostEqual(stop.latlong.y, 54.5950542848164)

        stop = stops.get(atco_code="8460TR000124")
        self.assertEqual(stop.common_name, "Supermac's")
        self.assertEqual(stop.street, "Bridge Street")
        self.assertEqual(stop.crossing, "")
        self.assertEqual(stop.indicator, "Opp")
        self.assertEqual(stop.bearing, "")
        self.assertEqual(stop.timing_status, "")
        self.assertEqual(stop.stop_type, "TXR")
        self.assertAlmostEqual(stop.latlong.x, -9.05469898181141)
        self.assertAlmostEqual(stop.latlong.y, 53.2719763661735)
        self.assertEqual(stop.admin_area_id, 846)
        self.assertEqual(stop.locality_id, "E0846001")

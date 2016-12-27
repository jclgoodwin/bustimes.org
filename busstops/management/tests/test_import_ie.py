"""Tests for importing Ireland stops and services
"""
import os
import zipfile
from django.test import TestCase
from django.core.management import call_command
from ...models import Region, AdminArea, Locality, StopPoint


DIR = os.path.dirname(os.path.abspath(__file__))
FIXTURES_DIR = os.path.join(DIR, 'fixtures')


class ImportIrelandTest(TestCase):
    """Test the import_ie_nptg and import_ie_nptg command
    """
    @classmethod
    def setUpTestData(cls):
        call_command('import_ie_nptg', os.path.join(FIXTURES_DIR, 'ie_nptg.xml'))

        with zipfile.ZipFile(os.path.join(FIXTURES_DIR, 'ie_naptan.zip'), 'a') as open_zipfile:
            open_zipfile.write(os.path.join(FIXTURES_DIR, 'ie_naptan.xml'))

        call_command('import_ie_naptan_xml', os.path.join(FIXTURES_DIR, 'ie_naptan.zip'))

    def test_regions(self):
        regions = Region.objects.all().order_by('name')
        self.assertEqual(len(regions), 5)
        self.assertEqual(regions[0].name, 'Connacht')
        self.assertEqual(regions[2].name, 'Munster')

    def test_areas(self):
        areas = AdminArea.objects.all().order_by('name')
        self.assertEqual(len(areas), 40)

        self.assertEqual(areas[0].name, 'Antrim')
        self.assertEqual(areas[0].region.name, 'Northern Ireland')

        self.assertEqual(areas[2].name, 'Carlow')
        self.assertEqual(areas[2].region.name, 'Leinster')

    def test_localities(self):
        localities = Locality.objects.all().order_by('name')
        self.assertEqual(len(localities), 3)
        self.assertEqual(localities[0].name, 'Dangan')
        self.assertEqual(localities[0].admin_area.name, 'Galway City')
        self.assertEqual(localities[0].latlong.x, -9.077645)
        self.assertEqual(localities[0].latlong.y, 53.290138)

        self.assertEqual(localities[2].name, 'Salthill')
        self.assertEqual(localities[2].admin_area.name, 'Galway City')
        self.assertEqual(localities[2].latlong.x, -9.070427)
        self.assertEqual(localities[2].latlong.y, 53.262565)

    def test_stops(self):
        stops = StopPoint.objects.all().order_by('atco_code')
        self.assertEqual(len(stops), 4)
        self.assertEqual(stops[0].atco_code, '700000004096')
        self.assertEqual(stops[0].common_name, 'Rathfriland')
        self.assertEqual(stops[0].stop_type, '')
        self.assertEqual(stops[0].bus_stop_type, '')
        self.assertEqual(stops[0].timing_status, '')
        self.assertEqual(stops[0].latlong.x, -6.15849970528097)
        self.assertEqual(stops[0].latlong.y, 54.236552528081)

        stop = stops.get(atco_code='700000015422')
        self.assertEqual(stop.common_name, 'Europa Buscentre Belfast')
        self.assertEqual(stop.street, 'Glengall Street')
        self.assertEqual(stop.crossing, '')
        self.assertEqual(stop.indicator, 'in')
        self.assertEqual(stop.bearing, '')
        self.assertEqual(stop.timing_status, 'OTH')
        self.assertEqual(stop.latlong.x, -5.93626793184173)
        self.assertEqual(stop.latlong.y, 54.5950542848164)

        stop = stops.get(atco_code='8460TR000124')
        self.assertEqual(stop.common_name, "Supermac's")
        self.assertEqual(stop.street, 'Bridge Street')
        self.assertEqual(stop.crossing, '')
        self.assertEqual(stop.indicator, 'opp')
        self.assertEqual(stop.bearing, '')
        self.assertEqual(stop.timing_status, '')
        self.assertEqual(stop.stop_type, 'TXR')
        self.assertEqual(stop.latlong.x, -9.05469898181141)
        self.assertEqual(stop.latlong.y, 53.2719763661735)
        self.assertEqual(stop.admin_area_id, 846)
        self.assertEqual(stop.locality_id, 'E0846001')

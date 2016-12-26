"""Tests for importing Ireland stops and services
"""
import os
from django.test import TestCase
from django.core.management import call_command
from ...models import Region, AdminArea, Locality


DIR = os.path.dirname(os.path.abspath(__file__))


class ImportNPTGTest(TestCase):
    """Test the import_ie_nptg command
    """
    @classmethod
    def setUpTestData(cls):
        call_command('import_ie_nptg', os.path.join(DIR, 'fixtures', 'ie_nptg.xml'))

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

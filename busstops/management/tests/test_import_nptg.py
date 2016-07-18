import os
from django.test import TestCase
from ..commands import import_regions, import_areas, import_districts
from ...models import Region, AdminArea, District


DIR = os.path.dirname(os.path.abspath(__file__))


class ImportNPTGTest(TestCase):
    """
    Test the import_regions, import_areas, import_districts and
    import_localities commands
    """
    @staticmethod
    def do_import(command, filename):
        filename = os.path.join(DIR, 'fixtures/%s.csv' % filename)
        with open(filename) as open_file:
            command.input = open_file
            command.handle()

    @classmethod
    def setUpTestData(cls):
        cls.do_import(import_regions.Command(), 'Regions')
        cls.do_import(import_areas.Command(), 'AdminAreas')
        cls.do_import(import_districts.Command(), 'Districts')

        cls.east_anglia = Region.objects.get(id='EA')
        cls.east_midlands = Region.objects.get(id='EM')
        cls.london = Region.objects.get(id='L')

        cls.cambs = AdminArea.objects.get(pk=71)
        cls.derby = AdminArea.objects.get(pk=17)

        cls.district = District.objects.get(pk=29)

    def test_regions(self):
        self.assertEqual(self.east_anglia.id, 'EA')
        self.assertEqual(self.east_anglia.the(), 'East Anglia')

        self.assertEqual(self.east_midlands.id, 'EM')
        self.assertEqual(self.east_midlands.the(), 'the East Midlands')

        self.assertEqual(self.london.id, 'L')
        self.assertEqual(self.london.the(), 'London')

    def test_areas(self):
        self.assertEqual(self.cambs.pk, 71)
        self.assertEqual(str(self.cambs), 'Cambridgeshire')
        self.assertEqual(str(self.cambs.region), 'East Anglia')

        self.assertEqual(self.derby.pk, 17)
        self.assertEqual(str(self.derby), 'Derby')
        self.assertEqual(self.derby.region.the(), 'the East Midlands')

    def test_districts(self):
        self.assertEqual(self.district.pk, 29)
        self.assertEqual(str(self.district), 'Cambridge')
        self.assertEqual(str(self.district.admin_area), 'Cambridgeshire')

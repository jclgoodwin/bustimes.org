"Tests for management commands."
from django.test import TestCase
from busstops.management.commands.import_stop_areas import Command
from busstops.models import Region, AdminArea

class ImportStopAreasTest(TestCase):
    "Test the import_stop_areas command."

    def test_row_to_stoparea(self):
        """"
        Given a row, does row_to_stoparea create an object in the database with the correct field
        values?
        """

        row = ['940GZZBKBON', 'Boness (Boness & Kinneil Railway)', '', '147', 'GTMU', 'U',
               '300332', '681714', '2007-02-06T14:15:00', '2007-02-06T14:15:00', '0', 'new', 'act']
        region = Region.objects.create(id='GB', name='Great Britain')
        admin_area = AdminArea.objects.create(id=147, atco_code=940, region=region)
        area, created = Command.row_to_stoparea(row)

        self.assertTrue(created)
        self.assertEqual(area.id, '940GZZBKBON')
        self.assertEqual(area.name, 'Boness (Boness & Kinneil Railway)')
        self.assertEqual(area.stop_area_type, 'GTMU')
        self.assertEqual(area.admin_area, admin_area)
        self.assertTrue(area.active)

        area, created = Command.row_to_stoparea(row)
        self.assertFalse(created)


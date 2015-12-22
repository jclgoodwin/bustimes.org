"Tests for management commands."
from django.test import TestCase
from busstops.management.commands import import_stop_areas
from busstops.models import Region, AdminArea


class ImportStopAreasTest(TestCase):
    "Test the import_stop_areas command."

    command = import_stop_areas.Command()

    def test_row_to_stoparea(self):
        "Given a row, does row_to_stoparea return a StopArea object with the correct field values?"

        row = {
            'GridType': 'U',
            'Status': 'act',
            'Name': 'Buscot Copse',
            'AdministrativeAreaCode': '064',
            'StopAreaType': 'GPBS',
            'NameLang': '',
            'StopAreaCode': '030G50780001',
            'Easting': '460097',
            'Modification': 'new',
            'ModificationDateTime': '2015-02-13T15:31:00',
            'CreationDateTime': '2015-02-13T15:31:00',
            'RevisionNumber': '0',
            'Northing': '171718'
        }
        region = Region.objects.create(id='GB', name='Great Britain')
        admin_area = AdminArea.objects.create(id=64, atco_code=30, region=region)
        area = self.command.handle_row(row)

        self.assertEqual(area.id, '030G50780001')
        self.assertEqual(area.name, 'Buscot Copse')
        self.assertEqual(area.stop_area_type, 'GPBS')
        self.assertEqual(area.admin_area, admin_area)
        self.assertTrue(area.active)
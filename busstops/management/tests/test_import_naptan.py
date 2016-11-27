"""Tests for importing NaPTAN data
"""

import os
from django.test import TestCase
from ...models import Region, AdminArea, StopPoint, Locality
from ..commands import update_naptan, import_stop_areas, import_stops


DIR = os.path.dirname(os.path.abspath(__file__))


class UpdateNaptanTest(TestCase):
    """Test the update_naptan command
    """
    command = update_naptan.Command()

    def test_get_old_rows(self):
        self.assertIsNone(self.command.get_old_rows())

    def test_get_diff(self):
        new_rows = [{
            'id': 1,
            'cell': [
                'S',
                'Aberdeen',
                '639',
                '07/06/2016',
                '1354',
                '143',
                '0',
                '0',
                '0',
                '0',
                '0',
                'V2',
                '7/17/2016'
            ]
        }]
        self.assertEqual(self.command.get_diff(new_rows, None), (['S'], ['639']))
        self.assertEqual(self.command.get_diff(new_rows, new_rows), ([], []))


class ImportStopAreasTest(TestCase):
    """Test the import_stop_areas command
    """
    command = import_stop_areas.Command()

    def test_row_to_stoparea(self):
        """
        Given a row, does row_to_stoparea return a StopArea object with the correct field values?
        """
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


class StopsTest(TestCase):
    """Test the import_stops command
    """
    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(id='GB', name='Great Britain')
        cls.admin_area = AdminArea.objects.create(id=34, atco_code=2, region_id='GB')
        cls.locality_1 = Locality.objects.create(id='E0054410', name='Baglan', admin_area_id=34)
        cls.locality_2 = Locality.objects.create(id='N0078801', name='Port Talbot', admin_area_id=34)

        command = import_stops.Command()
        command.input = os.path.join(DIR, 'fixtures/Stops.csv')
        command.handle()

    def test_imported_stops(self):
        legion = StopPoint.objects.get(pk='5820AWN26274')
        self.assertEqual(str(legion), 'The Legion (o/s)')
        self.assertEqual(legion.landmark, 'Port Talbot British Legion')
        self.assertEqual(legion.crossing, 'Eagle Street')
        self.assertEqual(legion.get_heading(), 315)

        plaza = StopPoint.objects.get(pk='5820AWN26259')
        self.assertEqual(plaza.get_qualified_name(), 'Port Talbot Plaza')
        self.assertEqual(plaza.landmark, 'Port Talbot British Legion')
        self.assertEqual(plaza.crossing, 'Eagle Street')
        self.assertEqual(plaza.get_heading(), 135)

        club = StopPoint.objects.get(pk='5820AWN26438')
        self.assertEqual(str(club), "Ty'n y Twr Club")

from django.test import TestCase
from ..commands import import_regions, import_districts, import_areas


class ImportRegions(TestCase):
    "Test the import_regions command."

    @classmethod
    def setUpTestData(cls):
        command = import_regions.Command()
        cls.east_anglia = command.handle_row({
            'RegionCode': 'EA',
            'RegionName': 'East Anglia',
            'RegionNameLang': '',
            'CreationDateTime': '2006-01-25T07:54:31',
            'RevisionNumber': '0',
            'ModificationDateTime': '2006-01-25T07:54:31',
            'Modification': ''
        })[0]
        cls.east_midlands = command.handle_row({
            'RegionCode': 'EM',
            'RegionName': 'East Midlands',
            'RegionNameLang': '',
            'CreationDateTime': '2006-01-25T07:54:31',
            'RevisionNumber': '0',
            'ModificationDateTime': '2006-01-25T07:54:31',
            'Modification': ''
        })[0]
        cls.london = command.handle_row({
            'RegionCode': 'L',
            'RegionName': 'London',
            'RegionNameLang': '',
            'CreationDateTime': '2006-01-25T07:54:31',
            'RevisionNumber': '0',
            'ModificationDateTime': '2006-01-25T07:54:31',
            'Modification': ''
        })[0]

    def test_regions(self):
        self.assertEqual(self.east_anglia.id, 'EA')
        self.assertEqual(self.east_anglia.the(), 'East Anglia')

        self.assertEqual(self.east_midlands.id, 'EM')
        self.assertEqual(self.east_midlands.the(), 'the East Midlands')

        self.assertEqual(self.london.id, 'L')
        self.assertEqual(self.london.the(), 'London')

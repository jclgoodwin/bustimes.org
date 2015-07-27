"Tests for management commands."
from django.test import TestCase
from busstops.management.commands import import_stop_areas
from busstops.management.commands import import_operators
from busstops.models import Region, AdminArea

class ImportStopAreasTest(TestCase):
    "Test the import_stop_areas command."

    command = import_stop_areas.Command()

    def test_row_to_stoparea(self):
        "Given a row, does row_to_stoparea return a StopArea object with the correct field values?"

        row = ['940GZZBKBON', 'Boness (Boness & Kinneil Railway)', '', '147', 'GTMU', 'U',
               '300332', '681714', '2007-02-06T14:15:00', '2007-02-06T14:15:00', '0', 'new', 'act']
        region = Region.objects.create(id='GB', name='Great Britain')
        admin_area = AdminArea.objects.create(id=147, atco_code=940, region=region)
        area = self.command.row_to_stoparea(row)

        self.assertEqual(area.id, '940GZZBKBON')
        self.assertEqual(area.name, 'Boness (Boness & Kinneil Railway)')
        self.assertEqual(area.stop_area_type, 'GTMU')
        self.assertEqual(area.admin_area, admin_area)
        self.assertTrue(area.active)

class ImportOperatorsTest(TestCase):
    command = import_operators.Command()

    def test_row_to_operator(self):
        """
        Is a strange NOC code (with an equals sign) correctly handled?

        Is the 'Admin' region correctly identified as 'GB'?

        Is an uninformative OperatorPublicName like 'First' ignored in favour of the
        OperatorReferenceName?

        Is the 'SC' region correctly identified as 'S' (Scotland)?
        """

        gb = Region.objects.create(id='GB', name='Great Britain')
        scotland = Region.objects.create(id='S', name='Scotland')

        row = ['=FC', 'First Capital Connect        ', '', '', '', '', '', '', '', '', '', '', 'Admin',
               'Rail', '', '', 'First']
        operator = self.command.row_to_operator(row)

        self.assertEqual(operator.id, 'FC')
        self.assertEqual(operator.name, 'First Capital Connect')
        self.assertEqual(operator.region, gb)

        row = ['FABD', 'First', 'First in Aberdeen', 'First Aberdeen Ltd', 'PM0000631', '', '', '',
               '', '', '', '', 'SC', 'Bus', '', '', 'First']
        operator = self.command.row_to_operator(row)

        self.assertEqual(operator.id, 'FABD')
        self.assertEqual(operator.name, 'First in Aberdeen')
        self.assertEqual(operator.region, scotland)

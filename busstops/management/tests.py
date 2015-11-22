"Tests for management commands."
from django.test import TestCase
from busstops.management.commands import import_stop_areas, import_operators, import_services
from busstops.models import Region, AdminArea


class ImportServicesTest(TestCase):
    """
    Tests for parts of the command that imports services from TNDS.
    """

    command = import_services.Command()

    def test_get_net(self):
        """
        Given a file name string
        get_net() should return a 2-3 character long string if appropriate,
        or '' otherwise.
        """

        data = [
            ('ea_21-2-_-y08-1.xml', 'ea'),
            ('ea_21-27-D-y08-1.xml', 'ea'),
            ('tfl_52-FL2-_-y08-1.xml', 'tfl'),
            ('suf_56-FRY-1-y08-15.xml', 'suf'),
            ('NATX_330.xml', ''),
            ('NE_130_PB2717_21A.xml', ''),
            ('SVRABAN007-20150620-9.xml', ''),
            ('SVRWLCO021-20121121-13693.xml', ''),
            ('National Express_NX_atco_NATX_T61.xml', ''),
            ('SnapshotNewportBus_TXC_2015714-0317_NTAO155.xml', ''),
            ]

        for file_name, net in data:
            self.assertEqual(self.command.get_net(file_name), net)


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

        row = ['=FC', 'First Capital Connect        ', '', '', '', '', '', '', '', '', '', '',
               'Admin', 'Rail', '', '', 'First']
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

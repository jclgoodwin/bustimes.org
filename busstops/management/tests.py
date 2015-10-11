"Tests for management commands."
from django.test import TestCase
from busstops.management.commands import import_stop_areas, import_operators, import_services
from busstops.models import Region, AdminArea


class ImportServicesTest(TestCase):
    """
    Tests for parts of the command that imports services from TNDS.
    """

    command = import_services.Command()

    def test_get_service_version_name(self):
        """
        Given a file name string (in one of several possible region-specific
        formats) does get_service_version_name() should return a shorter yet
        equally unique string.
        """

        data = [
            # W:
            ('SnapshotP&OLloyd_TXC_2015723-0507_FLBO023.xml', '2015723-0507_FLBO023'),
            ('SnapshotHDHutchinson&Son_TXC_2015723-0503_FLAB000.xml', '2015723-0503_FLAB000'),
            ('SnapshotConnect2_TXC_2015714-0306_CPAC001.xml', '2015714-0306_CPAC001'),
            ('SnapshotNewportBus_TXC_2015714-0317_NTAO155.xml', '2015714-0317_NTAO155'),
            ('SnapshotJohn\'sTravel(MT)_TXC_2015723-0503_MTAO020.xml', '2015723-0503_MTAO020'),
            ('P&OLloyd_TXC_2015723-0507_FLBO023.xml', '2015723-0507_FLBO023'),
            ('HDHutchinson&Son_TXC_2015723-0503_FLAB000.xml', '2015723-0503_FLAB000'),
            ('Connect2_TXC_2015714-0306_CPAC001.xml', '2015714-0306_CPAC001'),
            ('NewportBus_TXC_2015714-0317_NTAO155.xml', '2015714-0317_NTAO155'),
            ('John\'sTravel(MT)_TXC_2015723-0503_MTAO020.xml', '2015723-0503_MTAO020'),
            # EA, EM, L, WM, SE, SW:
            ('suf_56-FRY-1-y08-15.xml', '56-FRY-1-y08-15'),
            ('ea_21-27-D-y08-1.xml', '21-27-D-y08-1'),
            ('ea_21-2-_-y08-1.xml', '21-2-_-y08-1'),
            ('bed_52-FL2-_-y08-1.xml', '52-FL2-_-y08-1'),
            # NCSD:
            ('NATX_330.xml', 'NATX_330'),
            ('National Express_NX_atco_NATX_T61.xml', 'NATX_T61'),
            # Y, S
            ('SVRWLCO021-20121121-13693.xml', 'WLCO021-20121121-13693'),
            ('SVRABAN007-20150620-9.xml', 'ABAN007-20150620-9'),
            # NE:
            ('NE_130_PB2717_21A.xml', 'NE_130_PB2717_21A'),
            ]

        for file_name, name in data:
            self.assertEqual(self.command.get_service_version_name(file_name), name)

    def test_get_net(self):
        """
        Given a file name string
        get_net() should return a 2-3 character long string if appropriate,
        or None otherwise.
        """

        data = [
            ('ea_21-2-_-y08-1.xml',     'ea'),
            ('ea_21-27-D-y08-1.xml',    'ea'),
            ('tfl_52-FL2-_-y08-1.xml',  'tfl'),
            ('suf_56-FRY-1-y08-15.xml', 'suf'),
            ('NATX_330.xml',                  None),
            ('NE_130_PB2717_21A.xml',         None),
            ('SVRABAN007-20150620-9.xml',     None),
            ('SVRWLCO021-20121121-13693.xml', None),
            ('National Express_NX_atco_NATX_T61.xml', None),
            ('SnapshotNewportBus_TXC_2015714-0317_NTAO155.xml', None),
            ]

        for file_name, net in data:
            self.assertEqual(self.command.get_net(file_name), net)


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

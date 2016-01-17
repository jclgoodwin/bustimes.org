from django.test import TestCase
from busstops.management.commands import import_services


class ImportServicesTest(TestCase):
    """Tests for parts of the command that imports services from TNDS"""

    command = import_services.Command()

    def test_sanitize_description(self):

        testcases = (
            (
                'Bus Station bay 5,Blyth - Grange Road turning circle,Widdrington Station',
                'Blyth - Widdrington Station'
            ),
            (
                '      Bus Station-Std C,Winlaton - Ryton Comprehensive School,Ryton     ',
                'Winlaton - Ryton'
            ),
        )

        for inp, outp in testcases:
            self.assertEqual(self.command.sanitize_description(inp), outp)

    def test_get_net(self):
        """
        Given a file name string
        get_net() should return a 2-3 character long string if appropriate,
        or '' otherwise.
        """

        data = (
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
            ('ArrivaCymru51S-Rhyl-StBrigid`s-Denbigh1_TXC_2016108-0319_DGAO051S.xml', ''),
        )

        for file_name, net in data:
            self.assertEqual(self.command.get_net(file_name), net)


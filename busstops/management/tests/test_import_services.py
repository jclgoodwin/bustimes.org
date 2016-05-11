import os
import xml.etree.cElementTree as ET
from django.test import TestCase
from ...models import Operator, Service
from ..commands import import_services


DIR = os.path.dirname(os.path.abspath(__file__))


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

    def test_get_net_service_code_and_line_ver(self):
        """
        Given a file name string
        get_net() should return a (net, service_code, line_ver) tuple if appropriate,
        or ('', None, None) otherwise.
        """

        data = (
            ('ea_21-2-_-y08-1.xml', ('ea', 'ea_21-2-_-y08', '1')),
            ('ea_21-27-D-y08-1.xml', ('ea', 'ea_21-27-D-y08', '1')),
            ('tfl_52-FL2-_-y08-1.xml', ('tfl', 'tfl_52-FL2-_-y08', '1')),
            ('suf_56-FRY-1-y08-15.xml', ('suf', 'suf_56-FRY-1-y08', '15')),
            ('NATX_330.xml', ('', None, None)),
            ('NE_130_PB2717_21A.xml', ('', None, None)),
            ('SVRABAN007-20150620-9.xml', ('', None, None)),
            ('SVRWLCO021-20121121-13693.xml', ('', None, None)),
            ('National Express_NX_atco_NATX_T61.xml', ('', None, None)),
            ('SnapshotNewportBus_TXC_2015714-0317_NTAO155.xml', ('', None, None)),
            ('ArrivaCymru51S-Rhyl-StBrigid`s-Denbigh1_TXC_2016108-0319_DGAO051S.xml', ('', None, None)),
        )

        for file_name, parts in data:
            self.assertEqual(self.command.get_net_service_code_and_line_ver(file_name), parts)

    def test_do_service(self):
        whippet = Operator.objects.create(pk='WHIP', region_id='EA', name='Whippet Coaches')

        with open(os.path.join(DIR, 'fixtures/ea_20-45-A-y08-1.xml')) as file:
            root = ET.parse(file).getroot()

        self.command.do_service(root, 'EA', None)

        service = Service.objects.get(pk='ea_20-45-A-y08')

        self.assertEqual(str(service), '45 - Huntingdon - St Ives')
        self.assertTrue(service.show_timetable)
        self.assertEqual(service.operator.first(), whippet)
        self.assertEqual(service.get_traveline_url(), 'http://www.travelinesoutheast.org.uk/se/XSLT_TTB_REQUEST?line=20045&lineVer=1&net=ea&project=y08&sup=A&command=direct&outputFormat=0')

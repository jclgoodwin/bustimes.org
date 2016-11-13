"""Tests for importing Northern Ireland stops and services
"""
import os
from django.test import TestCase
from ...models import StopPoint
from ..commands import import_ni_stops, import_ni_services
from .test_import_nptg import ImportNPTGTest


DIR = os.path.dirname(os.path.abspath(__file__))


class ImportNornIronTest(TestCase):
    """Test the import_ni_stops command
    """
    @classmethod
    def setUpTestData(cls):
        ImportNPTGTest.do_import(import_ni_stops.Command(), 'bus-stop-list-february-2016')

        cls.mount_eagles = StopPoint.objects.get(atco_code='700000000000')
        cls.ni_stops = StopPoint.objects.filter(atco_code__startswith='7')

    def test_stops(self):
        self.assertEqual(self.mount_eagles.indicator, 'outward')
        self.assertEqual(self.mount_eagles.common_name, 'Mount Eagles')

        self.assertEqual(len(self.ni_stops), 9)


class ImportNIServcesTest(TestCase):
    """Test the import_ni_services command
    """
    command = import_ni_services.Command()

    def test_get_file_header(self):
        line = 'ATCO-CIF0500Metro                           OMNITIMES       20160802144451\n'
        self.assertEqual(self.command.get_file_header(line), {
            'file_type': 'ATCO-CIF',
            'version': '0500',
            'file_originator': 'Metro                           ',
            'source_product': 'OMNITIMES       ',
            'production_datetime': '20160802144451'
        })

    def test_get_route_description(self):
        line = 'QDNMET 1A  OCity Centre - Carnmoney - Fairview Road - Glenville                 \n'
        self.assertEqual(self.command.get_route_description(line), {
            'transaction_type': 'N',
            'operator': 'MET ',
            'route_number': '1A  ',
            'route_direction': 'O',
            'route_description': 'City Centre - Carnmoney - Fairview Road - Glenville                 \n'
        })

    def test_get_journey_header(self):
        line = 'QSNMET 0510  20160901201706301111100 X1A                        O\n'
        self.assertEqual(self.command.get_journey_header(line), {
            'transaction_type': 'N',
            'operator': 'MET ',
            'unique_journey_identifier': '0510  ',
            'direction': 'O\n',
        })

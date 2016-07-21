# coding=utf-8
import os
from django.test import TestCase
from ...models import StopPoint
from ..commands import import_ni_stops
from .test_import_nptg import ImportNPTGTest


DIR = os.path.dirname(os.path.abspath(__file__))


class ImportNornIronTest(TestCase):
    """
    Test the import_ni_stops command

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

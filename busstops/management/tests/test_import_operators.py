from django.test import TestCase
from busstops.management.commands import import_stop_areas, import_operators, import_services
from busstops.models import Region, AdminArea, Operator
import os


DIR = os.path.dirname(os.path.abspath(__file__))


class ImportOperatorsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        command = import_operators.Command()
        command.input = open(os.path.join(DIR, 'fixtures/NOC_DB.csv'))

        cls.great_britain = Region.objects.create(id='GB', name='Great Britain')
        cls.scotland = Region.objects.create(id='S', name='Scotland')
        Region.objects.create(id='SW', name='South West')

        command.handle()

        cls.first_aberdeen = Operator.objects.get(id='FABD')
        cls.c2c = Operator.objects.get(id='CC')
        cls.ace_travel = Operator.objects.get(id='ACER')

    def test_operator_id(self):
        """Is a strange NOC code (with an equals sign) correctly handled?"""
        self.assertEqual(self.c2c.id, 'CC')
        self.assertEqual(self.c2c.name, 'c2c')

    def test_operator_region(self):
        # Is the 'SC' region correctly identified as 'S' (Scotland)?
        self.assertEqual(self.first_aberdeen.region, self.scotland)

        # Is the 'Admin' region correctly identified as 'GB'?
        self.assertEqual(self.c2c.region, self.great_britain)

    def test_operator_name(self):
        """Is an uninformative OperatorPublicName like 'First' ignored in
        favour of the OperatorReferenceName?
        """
        self.assertEqual(self.first_aberdeen.name, 'First in Aberdeen')
        self.assertEqual(self.c2c.name, 'c2c')

    def test_operator_mode(self):
        """Is an operator mode like 'DRT' expanded correctly to 'demand responsive transport'?"""
        self.assertEqual(self.ace_travel.vehicle_mode, 'demand responsive transport')

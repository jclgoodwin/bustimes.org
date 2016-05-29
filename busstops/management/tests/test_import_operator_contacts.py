from django.test import TestCase
from ...models import Region, Operator
from ..commands import import_operator_contacts
import os


DIR = os.path.dirname(os.path.abspath(__file__))


class ImportOperatorContactTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.command = import_operator_contacts.Command()
        cls.command.input = open(os.path.join(DIR, 'fixtures/nocrecords.xml'))

        east_anglia = Region.objects.create(id='EA', name='East Anglia')
        Operator.objects.create(pk='SNDR', region=east_anglia)

        cls.command.handle()

    def test_format_address(self):
        self.assertEqual(
            self.command.format_address('8 Market Place, Hartlepool TS24 7SB'),
            '8 Market Place\nHartlepool\nTS24 7SB'
        ) 
        self.assertEqual(self.command.format_address('TS24 7SB'), 'TS24 7SB')

    def test_imported_data(self):
        sanders_coaches = Operator.objects.get(pk='SNDR')
        self.assertEqual(sanders_coaches.address, 'Sanders Coaches\nHeath Drive\nHolt\nNR25 6ER') 
        self.assertEqual(sanders_coaches.phone, '01263 712800')
        self.assertEqual(sanders_coaches.email, 'charles@sanderscoaches.com') 
        self.assertEqual(sanders_coaches.url, 'http://www.sanderscoaches.com') 

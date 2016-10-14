import os
from django.test import TestCase
from ...models import Region, Operator
from ..commands import import_operator_contacts


DIR = os.path.dirname(os.path.abspath(__file__))


class ImportOperatorContactTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.command = import_operator_contacts.Command()
        cls.command.input = os.path.join(DIR, 'fixtures', 'nocrecords.xml')

        east_anglia = Region.objects.create(id='EA', name='East Anglia')
        cls.sanders = Operator.objects.create(pk='SNDR', region=east_anglia)
        cls.first = Operator.objects.create(pk='FECS', region=east_anglia)

        cls.command.handle()

    def test_format_address(self):
        self.assertEqual(
            self.command.format_address('8 Market Place, Hartlepool TS24 7SB'),
            '8 Market Place\nHartlepool\nTS24 7SB'
        )
        self.assertEqual(self.command.format_address('TS24 7SB'), 'TS24 7SB')

    def test_imported_data(self):
        self.sanders.refresh_from_db()
        self.assertEqual(self.sanders.address, 'Sanders Coaches\nHeath Drive\nHolt\nNR25 6ER')
        self.assertEqual(self.sanders.phone, '01263 712800')
        self.assertEqual(self.sanders.email, 'charles@sanderscoaches.com')
        self.assertEqual(self.sanders.url, 'http://www.sanderscoaches.com')

        self.first.refresh_from_db()
        self.assertEqual(self.first.address, '')
        self.assertEqual(self.first.phone, '')
        self.assertEqual(self.first.email, '')
        self.assertEqual(self.first.url, 'https://www.firstgroup.com/norfolk-suffolk')

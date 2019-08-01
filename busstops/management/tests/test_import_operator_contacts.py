import os
from django.test import TestCase
from ...models import Region, Operator, DataSource, OperatorCode
from ..commands import import_operator_contacts


DIR = os.path.dirname(os.path.abspath(__file__))


class ImportOperatorContactTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.command = import_operator_contacts.Command()
        cls.command.input = os.path.join(DIR, 'fixtures', 'nocrecords.xml')

        east_anglia = Region.objects.create(id='EA', name='East Anglia')

        cls.sanders = Operator.objects.create(pk='CACK', name='Sanders', region=east_anglia)
        cls.first = Operator.objects.create(pk='CRAP', name='First', region=east_anglia)
        cls.loaches = Operator.objects.create(pk='SHIT', name='Loaches Coaches', region=east_anglia)
        cls.polruan = Operator.objects.create(pk='POOP', name='Polruan', region=east_anglia)

        source = DataSource.objects.create(name='National Operator Codes', datetime='2017-01-01 00:00+00:00')

        OperatorCode.objects.create(operator=cls.sanders, code='SNDR', source=source)
        OperatorCode.objects.create(operator=cls.first, code='FECS', source=source)
        OperatorCode.objects.create(operator=cls.loaches, code='LCHS', source=source)
        OperatorCode.objects.create(operator=cls.polruan, code='CSTL', source=source)

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
        self.assertEqual(self.sanders.twitter, 'SandersCoaches')

        self.first.refresh_from_db()
        self.assertEqual(self.first.address, '')
        self.assertEqual(self.first.phone, '')
        self.assertEqual(self.first.email, '')
        self.assertEqual(self.first.url, 'https://www.firstgroup.com/norfolk-suffolk')

        self.loaches.refresh_from_db()
        self.assertEqual(self.loaches.address, '')
        self.assertEqual(self.loaches.phone, '5678')
        self.assertEqual(self.loaches.email, '')
        self.assertEqual(self.loaches.url, 'http://www.arrivabus.co.uk')

        self.polruan.refresh_from_db()
        self.assertEqual(self.polruan.address, 'Toms Yard\nEast Street\nPolruan\nCornwall\nPL23 1BP')
        self.assertEqual(self.polruan.phone, '01726 870232')
        self.assertEqual(self.polruan.email, 'enquiries@ctomsandson.co.uk')
        self.assertEqual(self.polruan.url, '')

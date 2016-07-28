from django.test import TestCase
from ...models import Region, Operator, Service
from ..commands import correct_operator_regions  


class CorretcOperatorRegionsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.command = correct_operator_regions.Command()

        cls.east_midlands = Region.objects.create(id='EM', name='East Midlands')
        cls.west_midlands = Region.objects.create(id='WM', name='West Midlands')
        cls.middle_east = Region.objects.create(id='ME', name='Middle East')

        cls.goodwins = Operator.objects.create(
            region=cls.east_midlands,
            pk='GDWN',
            name='Go Goodwins'
        )
        cls.tellings = Operator.objects.create(
            region=cls.east_midlands,
            pk='TGML',
            name='Tellings Golden Miller'
        )

        cls.west_midlands_service = Service.objects.create(
            service_code='1',
            region=cls.west_midlands,
            date='2016-05-05'
        )
        cls.west_midlands_service.operator.set([cls.goodwins])

    def test_handle(self):
        self.assertEqual(self.goodwins.region_id, 'EM')
        self.assertEqual(self.tellings.region_id, 'EM')

        self.command.handle()

        self.assertEqual(Operator.objects.get(id='GDWN').region_id, 'WM')
        self.assertEqual(Operator.objects.get(id='TGML').region_id, 'EM')

    def test_maybe(self):
        self.assertEqual(self.tellings.region_id, 'EM')

        self.assertEqual(
            'consider moving Tellings Golden Miller from East Midlands to [<Region: Middle East>, <Region: West Midlands>]',
            self.command.maybe_move_operator(self.tellings, [self.middle_east, self.west_midlands])
        )


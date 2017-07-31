from warnings import catch_warnings
from django.test import TestCase
from django.core.management import call_command
from .models import Region, AdminArea, Locality, Operator, Service
from .search_indexes import LocalityIndex, OperatorIndex, ServiceIndex


class SearchIndexTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        region = Region.objects.create(id='EN', name='England')
        area = AdminArea.objects.create(id=1, atco_code=1, region=region, name='England')
        cls.pontypandy = Locality.objects.create(admin_area=area, name='Pontypandy')
        cls.richards = Operator.objects.create(region=region, name='Richards')
        cls.service = Service.objects.create(date='2017-02-02', region=region)
        cls.old_service = Service.objects.create(service_code='old', date='2017-02-02', region=region, current=False)

    def test_locality_index(self):
        self.assertEqual(1, len(LocalityIndex().read_queryset()))
        self.assertEqual(0, len(LocalityIndex().index_queryset()))

    def test_operator_index(self):
        self.assertEqual(1, len(OperatorIndex().read_queryset()))
        self.assertEqual(0, len(OperatorIndex().index_queryset()))

    def test_service_index(self):
        self.assertEqual(2, len(ServiceIndex().read_queryset()))
        self.assertEqual(1, len(ServiceIndex().index_queryset()))

    def test_command(self):
        with catch_warnings(record=True) as caught_warnings:
            call_command('update_search_indexes')
            self.assertEqual(1, len(caught_warnings))
            self.assertEqual(str(caught_warnings[0].message), 'remove is not implemented in this backend')

"""Tests for utilities and date ranges"""
from django.test import TestCase
from busstops.models import Region, Service
from .utils import get_pickle_filenames


FIXTURES_DIR = './busstops/management/tests/fixtures/'


class UtilsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.north_east = Region.objects.create(pk='NE')
        cls.north_west = Region.objects.create(pk='NW')
        cls.east_anglia = Region.objects.create(pk='EA')
        cls.great_britain = Region.objects.create(pk='GB')
        cls.south_west = Region.objects.create(pk='SW')

        cls.ne_service = Service.objects.create(
            pk='NE_130_PC4736_572',
            region_id='NE',
            date='2016-05-05'
        )
        cls.nw_service = Service.objects.create(
            pk='60023943',
            region_id='NW',
            date='2016-05-24'
        )
        cls.ea_service = Service.objects.create(
            pk='ea_21-13B-B-y08',
            region_id='EA',
            date='2016-05-24',
            net='ea'
        )
        cls.gb_service = Service.objects.create(
            pk='M11A_MEGA',
            region_id='GB',
            date='2016-05-24',
        )
        cls.sw_service = Service.objects.create(
            pk='swe_31-668-_-y10',
            region_id='SW',
            date='2016-05-24',
        )

    def test_get_pickle_filenames(self):
        """
        get_pickle_filenames should get filenames for a service,
        using different heuristics depending on the service's region
        """
        self.assertEqual(get_pickle_filenames(self.ne_service, None), ['NE_130_PC4736_572'])
        self.assertEqual(get_pickle_filenames(self.nw_service, None), ['SVR60023943'])

        self.assertEqual(get_pickle_filenames(self.ea_service, 'poo'), [])
        ea_filenames = get_pickle_filenames(self.ea_service, FIXTURES_DIR)
        self.assertEqual(['ea_21-13B-B-y08-1.xml'], ea_filenames)

        gb_filenames = get_pickle_filenames(self.gb_service, FIXTURES_DIR)
        self.assertEqual([], gb_filenames)

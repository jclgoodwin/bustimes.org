"""Tests for utilities and date ranges"""
from django.test import TestCase
from busstops.models import Region, Service
from .utils import sign_url, get_pickle_filenames, get_files_from_zipfile


FIXTURES_DIR = './busstops/management/tests/fixtures/'


class UtilsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.north_east = Region.objects.create(pk='NE')
        cls.scotland = Region.objects.create(pk='S')
        cls.east_anglia = Region.objects.create(pk='EA')
        cls.great_britain = Region.objects.create(pk='GB')
        cls.south_west = Region.objects.create(pk='SW')

        cls.ne_service = Service.objects.create(
            pk='NE_130_PC4736_572',
            region_id='NE',
            date='2016-05-05'
        )
        cls.s_service = Service.objects.create(
            pk='FIAX059',
            region_id='S',
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

    def test_sign_url(self):
        self.assertEqual(
            sign_url('http://example.com/?horse=1', 'fish'),
            'http://example.com/?horse=1&signature=s0RjLnH0GnQYwPTrUuoxZ1MfeRg='
        )

    def test_get_pickle_filenames(self):
        """get_pickle_filenames should get filenames for a service,
        using different heuristics depending on the service's region
        """
        self.assertEqual(get_pickle_filenames(self.ne_service, None), ['NE_130_PC4736_572'])
        self.assertEqual(get_pickle_filenames(self.s_service, None), ['SVRFIAX059'])

        self.assertEqual(get_pickle_filenames(self.ea_service, 'poo'), [])
        ea_filenames = get_pickle_filenames(self.ea_service, FIXTURES_DIR)
        self.assertEqual(['ea_21-13B-B-y08-1.xml'], ea_filenames)

        gb_filenames = get_pickle_filenames(self.gb_service, FIXTURES_DIR)
        self.assertEqual([], gb_filenames)

    def test_get_files_from_zipfile(self):
        with self.assertRaises(FileNotFoundError):
            self.assertEqual([], get_files_from_zipfile(self.ne_service))

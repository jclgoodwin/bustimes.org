# coding=utf-8
"""Tests for importing Ouibus and FlixBus stops and services
"""
import os
import zipfile
import vcr
from django.test import TestCase, override_settings
from ...models import Region, StopPoint, Service
from ..commands import import_ouibus_gtfs, import_ie_gtfs


FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


@override_settings(DATA_DIR=FIXTURES_DIR)
class ImpportGTFSTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.france = Region.objects.create(id='FR', name='France')

        cls.dir_path = os.path.join(FIXTURES_DIR, 'flixbus')
        cls.feed_path = cls.dir_path + '.zip'
        with zipfile.ZipFile(cls.feed_path, 'a') as open_zipfile:
            for item in os.listdir(cls.dir_path):
                open_zipfile.write(os.path.join(cls.dir_path, item), item)

        command = import_ouibus_gtfs.Command()
        command.handle_zipfile(cls.feed_path, 'flixbus')

    def test_download_if_modified(self):
        path = 'download_if_modified.txt'
        url = 'https://bustimes.org.uk/static/js/global.js'

        self.assertFalse(os.path.exists(path))

        with vcr.use_cassette('data/vcr/download_if_modified.yaml'):
            self.assertTrue(import_ie_gtfs.download_if_modified(path, url))
            self.assertFalse(import_ie_gtfs.download_if_modified(path, url))

        self.assertTrue(os.path.exists(path))

        os.remove(path)

    def test_stops(self):
        stops = StopPoint.objects.all()
        self.assertEqual('flixbus-10', stops[0].atco_code)

        self.assertEqual('Turin, Torino (Lingotto)', stops[1].common_name)
        self.assertEqual('Rust (Europa-Park), Rust (Europa park)', stops[3].common_name)
        self.assertEqual('Luxembourg Kirchberg', stops[9].common_name)

    def test_services(self):
        services = Service.objects.all()
        self.assertEqual(services[0].service_code, 'flixbus-001')
        self.assertEqual(services[0].line_name, 'FlixBus')

        stops = services[0].stops.all()
        self.assertEqual(7, len(stops))

    @classmethod
    def tearDownClass(cls):
        """Delete the GTFS feed zip file and SQLite database."""
        super(ImpportGTFSTest, cls).tearDownClass()

        os.remove(cls.feed_path)
        os.remove(os.path.join(FIXTURES_DIR, 'gtfs.sqlite'))

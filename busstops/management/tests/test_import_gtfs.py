# coding=utf-8
"""Tests for importing Ouibus and FlixBus stops and services
"""
import os
import zipfile
import vcr
from django.test import TestCase, override_settings
from django.core.management import call_command
from ...models import StopPoint, Service
from ..commands import import_ie_gtfs


FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


@override_settings(DATA_DIR=FIXTURES_DIR)
class ImpportGTFSTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        for collection in ('ouibus', 'flixbus'):
            dir_path = os.path.join(FIXTURES_DIR, collection)
            feed_path = dir_path + '.zip'
            with zipfile.ZipFile(feed_path, 'a') as open_zipfile:
                for item in os.listdir(dir_path):
                    open_zipfile.write(os.path.join(dir_path, item), item)

        with vcr.use_cassette(os.path.join(FIXTURES_DIR, 'ouibus_gtfs.yaml')):
            call_command('import_ouibus_gtfs', '--force')

        for collection in ('ouibus', 'flixbus'):
            path = os.path.join(FIXTURES_DIR, collection) + '.zip'
            os.remove(path)

    def test_download_if_modified(self):
        path = 'download_if_modified.txt'
        url = 'https://bustimes.org.uk/static/js/global.js'

        self.assertFalse(os.path.exists(path))

        with vcr.use_cassette('data/vcr/download_if_modified.yaml'):
            self.assertTrue(import_ie_gtfs.download_if_modified(path, url))
            self.assertFalse(import_ie_gtfs.download_if_modified(path, url))

        self.assertTrue(os.path.exists(path))

        os.remove(path)

    def test_flixbus_stops(self):
        self.assertEqual(11, StopPoint.objects.all().count())

        for atco_code, name, desc in (
            ('10', 'Munich central bus station', 'Arnulfstraße 21'),
            ('10438', 'Turin, Torino (Lingotto)', 'Via Mario Pannunzio'),
            ('15', 'Rust (Europa park)', 'Rheinweg'),
            ('93', 'Luxembourg Kirchberg', '4 Rue Alphonse Weicker'),
            ('11288', 'Plitvice Lakes (Plitvička Jezera)', 'D1 23')
        ):
            stop = StopPoint.objects.get(atco_code='flixbus-' + atco_code)
            self.assertEqual(stop.common_name, name)
            self.assertEqual(stop.crossing, desc)

    def test_flixbus_services(self):
        services = Service.objects.all()
        self.assertEqual(services[0].service_code, 'flixbus-001')
        self.assertEqual(services[0].line_name, 'FlixBus')

        stops = services[0].stops.all()
        self.assertEqual(18, len(stops))

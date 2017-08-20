# coding=utf-8
"""Tests for importing Ouibus and FlixBus stops and services
"""
import os
import zipfile
import vcr
from django.test import TestCase, override_settings
from django.core.management import call_command
from django.conf import settings
from ...models import StopPoint, Service
from ..commands import import_ie_gtfs


FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


@override_settings(
    DATA_DIR=FIXTURES_DIR,
    FRANCE_COLLECTIONS={
        'flixbus': settings.FRANCE_COLLECTIONS['flixbus'],
        'ouibus': settings.FRANCE_COLLECTIONS['ouibus'],
    }
)
class ImpportGTFSTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        for collection in settings.FRANCE_COLLECTIONS:
            dir_path = os.path.join(FIXTURES_DIR, collection)
            feed_path = dir_path + '.zip'
            with zipfile.ZipFile(feed_path, 'a') as open_zipfile:
                for item in os.listdir(dir_path):
                    open_zipfile.write(os.path.join(dir_path, item), item)

        with vcr.use_cassette(os.path.join(FIXTURES_DIR, 'ouibus_gtfs.yaml')):
            call_command('import_ouibus_gtfs', '--force')

        for collection in settings.FRANCE_COLLECTIONS:
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

    def test_stops(self):
        self.assertEqual(14, StopPoint.objects.all().count())

        for atco_code, name, desc in (
            ('flixbus-10', 'Munich central bus station', 'Arnulfstraße 21'),
            ('flixbus-10438', 'Turin, Torino (Lingotto)', 'Via Mario Pannunzio'),
            ('flixbus-15', 'Rust (Europa park)', 'Rheinweg'),
            ('flixbus-93', 'Luxembourg Kirchberg', '4 Rue Alphonse Weicker'),
            ('flixbus-11288', 'Plitvice Lakes (Plitvička Jezera)', 'D1 23'),
            ('ouibus-1', 'Paris Bercy (centre ville)', ''),
            ('ouibus-82', 'Parc Astérix', ''),
            ('ouibus-11', 'Lille', ''),
        ):
            stop = StopPoint.objects.get(atco_code=atco_code)
            self.assertEqual(stop.common_name, name)
            self.assertEqual(stop.crossing, desc)

    def test_services(self):
        services = Service.objects.order_by('service_code')
        self.assertEqual(services[0].service_code, 'flixbus-001')
        self.assertEqual(services[0].line_name, 'FlixBus')
        self.assertEqual(services[0].description, 'Freiburg - München')

        self.assertEqual(services[1].service_code, 'ouibus-1')
        self.assertEqual(services[1].line_name, 'Ouibus')
        self.assertEqual(services[1].description, 'Paris Bercy (centre ville) - Lille')

        stops = services[1].stops.all()
        self.assertEqual(3, len(stops))

# coding=utf-8
"""Tests for importing Ouibus and FlixBus stops and services
"""
import os
import vcr
from django.test import TestCase
from pygtfs.gtfs_entities import Stop
from ..commands import import_ouibus_gtfs, import_ie_gtfs


class ImpportGTFSTest(TestCase):
    def test_download_if_modified(self):
        path = 'download_if_modified.txt'
        url = 'https://bustimes.org.uk/static/js/global.js'

        self.assertFalse(os.path.exists(path))

        with vcr.use_cassette('data/vcr/download_if_modified.yaml'):
            self.assertTrue(import_ie_gtfs.download_if_modified(path, url))
            self.assertFalse(import_ie_gtfs.download_if_modified(path, url))

        self.assertTrue(os.path.exists(path))

        os.remove(path)

    def test_stop_id(self):
        stop = Stop(id='FLIXBUS:001')
        self.assertEqual(import_ouibus_gtfs.Command.get_stop_id('flixbus', stop), 'flixbus-001')
        stop.id = '002'
        self.assertEqual(import_ouibus_gtfs.Command.get_stop_id('ouibus', stop), 'ouibus-002')

    def test_stop_name(self):
        self.assertEqual(import_ouibus_gtfs.Command.get_stop_name({
            'stop_name': 'Rimini, Rimini-Marebello'
        }), 'Rimini-Marebello')
        self.assertEqual(import_ouibus_gtfs.Command.get_stop_name({
            'stop_name': 'Bâle Aéroport'
        }), 'Bâle Aéroport')

    def test_service_id(self):
        self.assertEqual(import_ouibus_gtfs.Command.get_service_id('flixbus', {
            'route_id': 'FLIXBUS:002'
        }), 'flixbus-002')
        self.assertEqual(import_ouibus_gtfs.Command.get_service_id('ouibus', {
            'route_id': '140'
        }), 'ouibus-140')

# coding=utf-8
"""Tests for importing Ouibus and FlixBus stops and services
"""
from django.test import TestCase
from ..commands import import_ouibus_gtfs


class ImpportGTFSTest(TestCase):
    def test_stop_id(self):
        self.assertEqual(import_ouibus_gtfs.Command.get_stop_id('flixbus', {
            'stop_id': 'FLIXBUS:001'
        }), 'flixbus-001')
        self.assertEqual(import_ouibus_gtfs.Command.get_stop_id('ouibus', {
            'stop_id': '001'
        }), 'ouibus-001')

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

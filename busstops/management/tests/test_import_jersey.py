import os
import vcr
from mock import patch
from django.test import TestCase, override_settings
from django.core.management import call_command
from ...models import StopPoint, Service


FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


class ImportJerseyTest(TestCase):
    @classmethod
    @patch('time.sleep', return_value=None)
    def setUpTestData(cls, _):
        with override_settings(DATA_DIR=FIXTURES_DIR):
            with vcr.use_cassette(os.path.join(FIXTURES_DIR, 'jersey.yaml')):
                call_command('import_jersey')

    def test_import_jersey_stops(self):
        self.assertEqual(82, StopPoint.objects.all().count())

        stop = StopPoint.objects.get(atco_code='je-2684')
        self.assertEqual(stop.indicator, 'S-bound')
        self.assertEqual(stop.bearing, 'S')

    def test_import_jersey_services(self):
        service = Service.objects.get(pk='je-1')
        self.assertEqual(str(service), '1 - Liberation Station -  Gorey Pier')
        self.assertEqual(service.stops.all().count(), 84)
        self.assertEqual(service.stops.filter(stopusage__timing_status='PTP').count(), 20)
        self.assertEqual(service.stops.filter(stopusage__timing_status='OTH').count(), 64)
        self.assertEqual(service.stops.filter(stopusage__direction='outbound').count(), 44)
        self.assertEqual(service.stops.filter(stopusage__direction='inbound').count(), 40)
        self.assertTrue(service.geometry)

"""Tests for importing Northern Ireland stops and services
"""
import os
import vcr
from django.test import TestCase
from ...models import StopPoint, Region, AdminArea, Service, StopUsage
from ..commands import import_ni_stops, enhance_ni_stops
from .test_import_nptg import ImportNPTGTest


DIR = os.path.dirname(os.path.abspath(__file__))


class ImportNornIronTest(TestCase):
    """Test the import_ni_stops command
    """
    @classmethod
    def setUpTestData(cls):
        ImportNPTGTest.do_import(import_ni_stops.Command(), 'bus-stop-list-february-2016')

        cls.mount_eagles = StopPoint.objects.get(atco_code='700000000000')
        cls.ni_stops = StopPoint.objects.filter(atco_code__startswith='700')
        cls.ni = Region(id='NI', name='Northern Ireland').save()

        # Create a dummy active service
        cls.service = Service.objects.create(service_code='DUMMY', date='2016-12-27', region_id='NI')
        # Use a stop which is near a landmark
        StopUsage.objects.create(service=cls.service, stop_id='700000000007', order=0)

        AdminArea.objects.create(region_id='NI', id='700', atco_code='700', name='Down')

    def test_stops(self):
        self.assertEqual(self.mount_eagles.indicator, 'outward')
        self.assertEqual(self.mount_eagles.common_name, 'Mount Eagles')

        self.assertEqual(len(self.ni_stops), 9)

    def test_enhance_stops(self):
        command = enhance_ni_stops.Command()
        command.delay = 0
        with vcr.use_cassette(os.path.join(DIR, 'fixtures', 'enhance_ni_stops.yaml')):
            command.handle()

        stop = StopPoint.objects.get(atco_code='700000000007')

        self.assertEqual(stop.street, 'Newtownards Road')
        self.assertEqual(stop.landmark, 'Dr Pitt Memorial Park')
        self.assertEqual(stop.town, '')

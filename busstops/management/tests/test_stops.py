"Tests for management commands."
import os
from django.test import TestCase
from ...models import StopPoint
from ..commands import import_stops, clean_stops


DIR = os.path.dirname(os.path.abspath(__file__))


class StopsTest(TestCase):
    "Test the import_stops and clean_stops commands."

    @classmethod
    def setUpTestData(cls):
        command = import_stops.Command()
        command.input = open(os.path.join(DIR, 'fixtures/Stops.csv'))
        command.handle()

    def test_imported_stops(self):
        cassell_road = StopPoint.objects.get(pk='010000001')
        self.assertEqual(str(cassell_road), 'Cassell Road (SW-bound)')
        self.assertEqual(cassell_road.get_heading(), 225)

        ring_o_bells = StopPoint.objects.get(pk='0610VR1022')
        self.assertEqual(str(ring_o_bells), 'Ring O`Bells (o/s)')
        self.assertEqual(ring_o_bells.landmark, 'Ring O`Bells')

    def test_clean_stops(self):
        clean_stops.Command().handle()

        cassell_road = StopPoint.objects.get(pk='010000001')
        self.assertEqual(str(cassell_road), 'Cassell Road (SW-bound)')

        ring_o_bells = StopPoint.objects.get(pk='0610VR1022')
        self.assertEqual(str(ring_o_bells), 'Ring O\'Bells (o/s)')
        self.assertEqual(ring_o_bells.landmark, 'Ring O\'Bells')

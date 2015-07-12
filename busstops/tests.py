from django.test import TestCase
from busstops.models import Region


class RegionTests(TestCase):

    def test_the(self):
        "Regions with certain names should have 'the' prepended, and others shouldn't."

        # Create some regions
        midlands = Region.objects.create(id='NM', name='North Midlands')
        east = Region.objects.create(id='ME', name='Middle East')
        ireland = Region.objects.create(id='IE', name='Ireland')

        # Use their names in a sentence
        self.assertEqual(midlands.the(), 'the North Midlands')
        self.assertEqual(east.the(), 'the Middle East')
        self.assertEqual(ireland.the(), 'Ireland')

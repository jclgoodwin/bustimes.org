from django.test import TestCase
from .models import Region, Locality


class RegionTests(TestCase):

    def test_string(self):
        midlands = Region.objects.create(id='NM', name='North Midlands')
        self.assertEqual(str(midlands), 'North Midlands')

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

    def test_get_absolute_url(self):
        midlands = Region.objects.create(id='NM', name='North Midlands')
        self.assertEqual(midlands.get_absolute_url(), '/regions/NM')


class LocalityTests(TestCase):

    def test_get_qualified_name(self):
        brinton = Locality.objects.create(id='1', name='Brinton')
        york = Locality.objects.create(id='2', name='York', qualifier_name='York')

        self.assertEqual(str(brinton), 'Brinton')
        self.assertEqual(str(york), 'York')

        self.assertEqual(brinton.get_qualified_name(), 'Brinton')
        self.assertEqual(york.get_qualified_name(), 'York, York')

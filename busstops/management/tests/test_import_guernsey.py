import os
import vcr
from mock import patch
from django.test import TestCase, override_settings
from django.core.management import call_command
from ...models import StopPoint, Service


FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


class ImportGuernseyTest(TestCase):
    @classmethod
    @patch('time.sleep', return_value=None)
    def setUpTestData(cls, _):
        with override_settings(DATA_DIR=FIXTURES_DIR):
            with vcr.use_cassette(os.path.join(FIXTURES_DIR, 'guernsey.yaml')):
                call_command('import_guernsey')

    def test_import_guernsey_stops(self):
        self.assertEqual(52, StopPoint.objects.all().count())

        town_terminus_c = StopPoint.objects.get(pk='gg-890000773')
        town_terminus = StopPoint.objects.get(pk='gg-890000487')

        self.assertEqual(town_terminus_c.latlong, town_terminus.latlong)
        self.assertEqual(town_terminus_c.service_set.count(), 1)
        self.assertEqual(town_terminus.service_set.count(), 1)

        bordeaux_harbour = StopPoint.objects.get(pk='gg-890000355')
        self.assertEqual(str(bordeaux_harbour.latlong), 'SRID=4326;POINT (-2.50857613778 49.4904331747)')
        self.assertEqual(bordeaux_harbour.indicator, 'Southbound')

    def test_import_guernsey_services(self):
        service = Service.objects.get(pk='gg-11')
        self.assertEqual(service.line_name, '11')
        self.assertTrue(service.geometry)

        response = self.client.get(service.get_absolute_url())
        self.assertContains(response, 'Guernsey Buses')
        self.assertContains(response, """
            <li class="OTH" itemscope itemtype="https://schema.org/BusStop">
                <a href="/stops/gg-890000560">
                    <span itemprop="name">Glategny Esplanade (Northbound)</span>
                </a>
            </li>
        """, html=True)
        self.assertContains(response, """
            <li class="PTP" itemscope itemtype="https://schema.org/BusStop">
                <a href="/stops/gg-890000487">
                    <span itemprop="name">Town Terminus</span>
                    <span itemprop="geo" itemscope itemtype="https://schema.org/GeoCoordinates">
                        <meta itemprop="latitude" content="49.4536581719" />
                        <meta itemprop="longitude" content="-2.53547245654" />
                    </span>
                </a>
            </li>
        """, html=True)

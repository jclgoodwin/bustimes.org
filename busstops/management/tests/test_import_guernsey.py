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
    def setUpTestData(cls, sleep):
        with override_settings(DATA_DIR=FIXTURES_DIR):
            with vcr.use_cassette(os.path.join(FIXTURES_DIR, 'guernsey.yaml')):
                call_command('import_guernsey')
        assert sleep.called

    def test_import_guernsey_stops(self):
        self.assertEqual(52, StopPoint.objects.all().count())

        town_terminus_c = StopPoint.objects.get(pk='gg-890000773')
        town_terminus = StopPoint.objects.get(pk='gg-890000487')

        self.assertEqual(town_terminus_c.indicator, 'Stand C')
        self.assertEqual(town_terminus_c.latlong, town_terminus.latlong)
        self.assertEqual(town_terminus_c.service_set.count(), 1)
        self.assertEqual(town_terminus.service_set.count(), 1)

        bordeaux_harbour = StopPoint.objects.get(pk='gg-890000355')
        self.assertEqual(str(bordeaux_harbour.latlong), 'SRID=4326;POINT (-2.50857613778 49.4904331747)')
        self.assertEqual(bordeaux_harbour.indicator, 'S-bound')
        self.assertEqual(bordeaux_harbour.bearing, 'S')

    def test_import_guernsey_services(self):
        service = Service.objects.get(service_code='gg-11')
        self.assertEqual(service.line_name, '11')
        self.assertTrue(service.geometry)

        response = self.client.get(service.get_absolute_url())
        self.assertContains(response, 'Guernsey Buses')
        self.assertContains(response, """
            <li class="minor">
                <a href="/stops/gg-890000560">Glategny Esplanade (N-bound)</a>
            </li>
        """, html=True)
        self.assertContains(response, """
            <li>
                <a href="/stops/gg-890000487">Town Terminus</a>
            </li>
        """, html=True)

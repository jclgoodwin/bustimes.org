import os
import vcr
from django.test import TestCase, override_settings
from django.core.management import call_command
from ...models import StopPoint, Service, Place


FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


class ImportSingaporeTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        with override_settings(SINAPORE_KEY='1ZxMEhvVQoux7V2Aaea6eA=='):
            with vcr.use_cassette(os.path.join(FIXTURES_DIR, 'singapore.yaml')):
                call_command('import_singapore')

        call_command('import_singapore_places')

    def test_import_stops(self):
        self.assertEqual(499, StopPoint.objects.all().count())

        stop = StopPoint.objects.first()
        self.assertEqual(str(stop), 'AFT BRAS BASAH STN EXIT A')

    def test_import_services(self):
        service = Service.objects.get()
        self.assertEqual(service.operator.get().name, 'SBS Transit')
        self.assertEqual(service.slug, 'sg-sbst-10')

    def test_import_places(self):
        self.assertEqual(307, Place.objects.count())

        place = Place.objects.get(name='Central Singapore')
        response = self.client.get(place.get_absolute_url())

        self.assertContains(response, '<h1>Central Singapore</h1>')
        self.assertContains(response, 'Fort Canning')
        self.assertContains(response, 'Bayfront Subzone')

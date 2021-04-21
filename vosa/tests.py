import os
import mock
from django.test import TestCase, override_settings
from django.core.management import call_command
from busstops.models import Region, Operator
from .models import Licence


class VosaTest(TestCase):
    @override_settings(DATA_DIR=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures'))
    def test(self):
        with mock.patch('vosa.management.commands.import_vosa.download_if_changed', return_value=(True, None)):
            with self.assertNumQueries(4):
                call_command('import_vosa', 'F')

        # multiple trading names
        licence = Licence.objects.get(licence_number='PF0000705')
        self.assertEqual(licence.trading_name, "R O SIMONDS\nSimonds Coach& Travel\nSimonds Countrylink")

        Region.objects.create(id='SW', name='South West')
        operator = Operator.objects.create(region_id='SW', id='AINS', name="Ainsley's Chariots")
        operator.licences.add(licence)

        response = self.client.get('/licences/PF0000705')
        self.assertContains(response, "Ainsley's Chariots")
        self.assertContains(response, "<th>Trading name</th>")

        # licence
        response = self.client.get('/licences/PF1018256')
        self.assertEqual(54, len(response.context_data['registrations']))
        self.assertEqual(0, len(response.context_data['cancelled']))
        self.assertContains(response, 'SANDERS COACHES LIMITED')
        self.assertContains(response, 'Thorpe Market &amp; Roughton')

        # rss feed
        with self.assertNumQueries(2):
            response = self.client.get('/licences/PF1018256/rss')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'SANDERS COACHES LIMITED')

        # licence 404
        with self.assertNumQueries(1):
            response = self.client.get('/licences/PH102095')
        self.assertEqual(response.status_code, 404)

        # registration
        with self.assertNumQueries(3):
            response = self.client.get('/registrations/PF1018256/2')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'WIVETON, CLEY, BLAKENEY, MORSTON, FIELD DALLING, HINDRINGHAM AND THURSFORD')

        # registration 404
        with self.assertNumQueries(1):
            response = self.client.get('/registrations/PH1020951/d')
        self.assertEqual(response.status_code, 404)

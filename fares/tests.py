from pathlib import Path
from vcr import use_cassette
from django.test import TransactionTestCase
from django.core.management import call_command
from .models import Tariff, TimeInterval


class FaresTest(TransactionTestCase):
    def test_bod_netex(self):
        path = Path(__file__).resolve() / 'data'

        with use_cassette(str(path / 'bod_fares.yaml')):
            call_command('import_netex_fares', 'XCpEBAoqPDfVdYRoUahb3F2nEZTJJCULXZCPo5x8')

        tariff = Tariff.objects.get(name="A C Williams WM06 - single fares")

        # tariff detail view
        response = self.client.get(tariff.get_absolute_url())

        self.assertContains(response, "A C Williams WM06 - single fares")
        self.assertContains(response, "<td>£1.70</td>")
        self.assertContains(response, "RAF Cranwell")

        origins = list(response.context_data['form'].fields['origin'].choices)
        destinations = list(response.context_data['form'].fields['destination'].choices)

        origin = origins[6][0]
        destination = destinations[5][0]
        response = self.client.get(f'{tariff.get_absolute_url()}?origin={origin}&destination={destination}')

        self.assertContains(response, "<h3>RAF Cranwell to Cranwell</h3>")
        self.assertContains(response, "<p>adult single: £1.50</p>")

        # dataset detail view
        response = self.client.get(f'{tariff.source.get_absolute_url()}?origin={origin}&destination={destination}')
        self.assertContains(response, "<h3>RAF Cranwell to Cranwell</h3>")
        self.assertContains(response, "<p>adult single: £1.50</p>")

        # fares index
        response = self.client.get('/fares/')
        self.assertContains(response, '£1.40–£1.70')

        self.assertEqual(TimeInterval.objects.count(), 0)

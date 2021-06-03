from django.test import TestCase
from django.core.management import call_command
from .models import Tariff, TimeInterval


class FaresTest(TestCase):
    def test_netex(self):
        call_command('import_netex_fares', 'test')
        tariff = Tariff.objects.get(name="A C Williams WM06 - single fares")

        # tariff detail view
        response = self.client.get(tariff.get_absolute_url())

        self.assertContains(response, "A C Williams WM06 - single fares")
        self.assertContains(response, "<td>£1.70</td>")
        self.assertContains(response, "RAF Cranwell")

        origins = list(response.context_data['form'].fields['origin'].choices)
        destinations = list(response.context_data['form'].fields['destination'].choices)

        origin = origins[2][0]
        destination = destinations[3][0]
        response = self.client.get(f'{tariff.get_absolute_url()}?origin={origin}&destination={destination}')

        self.assertContains(response, "<p>RAF Cranwell to Cranwell:</p>")
        self.assertContains(response, "<p>adult single: £1.50</p>")

        # dataset detail view
        response = self.client.get(f'{tariff.source.get_absolute_url()}?origin={origin}&destination={destination}')
        self.assertContains(response, "<p>RAF Cranwell to Cranwell:</p>")
        self.assertContains(response, "<p>adult single: £1.50</p>")

        self.assertEqual(TimeInterval.objects.count(), 8)

        # fares index
        response = self.client.get('/fares/')
        self.assertContains(response, '£3.30–£7.00')

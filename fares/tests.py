from django.test import TestCase
from django.core.management import call_command
from .models import Tariff


class FaresTest(TestCase):
    def test_netex(self):
        call_command('import_netex_fares')

        tariff = Tariff.objects.first()

        response = self.client.get(tariff.get_absolute_url())

        self.assertContains(response, "A C Williams WM06 - single fares")
        self.assertContains(response, "<td>£1.70</td>")
        self.assertContains(response, "RAF Cranwell")

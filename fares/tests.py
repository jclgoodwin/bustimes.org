import os
from django.test import TestCase
from .management.commands import import_netex_fares
from .models import Tariff, DataSet


class FaresTest(TestCase):
    def test_netex(self):
        command = import_netex_fares.Command()

        base_dir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(base_dir, 'data')

        for filename in os.listdir(path):
            source = DataSet.objects.create(name=filename, datetime='2017-01-01T00:00:00Z')
            with open(os.path.join(path, filename), "rb") as open_file:
                command.handle_file(source, open_file)

        tariff = Tariff.objects.get(name="A C Williams WM06 - single fares")

        response = self.client.get(tariff.get_absolute_url())

        self.assertContains(response, "A C Williams WM06 - single fares")
        self.assertContains(response, "<td>£1.70</td>")
        self.assertContains(response, "RAF Cranwell")

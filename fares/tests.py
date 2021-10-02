from pathlib import Path
from vcr import use_cassette
from django.test import TestCase
from django.core.management import call_command
from busstops.models import Operator, Service
from .models import Tariff, TimeInterval


class FaresTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a_c_williams = Operator.objects.create(id='WMSA')
        cls.wm06 = Service.objects.create(line_name='wm06', current=True)
        cls.wm06.operator.add(cls.a_c_williams)

    def test_bod_netex(self):
        path = Path(__file__).resolve().parent / 'data'

        with use_cassette(str(path / 'bod_fares.yaml')):
            with self.assertLogs('fares.management.commands.import_netex_fares') as cm:
                call_command('import_netex_fares', 'XCpEBAoqPDfVdYRoUahb3F2nEZTJJCULXZCPo5x8')

        self.assertEqual(cm.output, [
            'INFO:fares.management.commands.import_netex_fares:https://data.bus-data.dft.gov.uk/'
            'api/v1/fares/dataset/?api_key=XCpEBAoqPDfVdYRoUahb3F2nEZTJJCULXZCPo5x8&status=published',
            'INFO:fares.management.commands.import_netex_fares:AC Williams_20201119 06:45:17',
            'INFO:fares.management.commands.import_netex_fares:WMSA5f312755_1601531796591.xml',
            'WARNING:fares.management.commands.import_netex_fares:Service matching query does not exist. WMSA WM07',
            'INFO:fares.management.commands.import_netex_fares:https://data.bus-data.dft.gov.uk/api/v1/fares/'
            'dataset/?api_key=XCpEBAoqPDfVdYRoUahb3F2nEZTJJCULXZCPo5x8&limit=1&noc=WMSA&offset=1&status=published',
            'INFO:fares.management.commands.import_netex_fares:AC Williams_20201119 06:46:57',
            'INFO:fares.management.commands.import_netex_fares:WMSA6d2afadf_1601465195796.xml'
        ])

        tariff = Tariff.objects.get(name="A C Williams WM06 - single fares")

        self.assertEqual(self.wm06, tariff.services.get())

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

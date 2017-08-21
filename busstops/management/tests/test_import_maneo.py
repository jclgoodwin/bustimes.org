import os
import vcr
from django.test import TestCase
from ...models import Region, StopPoint, Service
from ..commands import import_maneo_stops


FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


class ImportManeoTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        command = import_maneo_stops.Command()

        Region.objects.create(id='FR')

        with vcr.use_cassette(os.path.join(FIXTURES_DIR, 'maneo.yaml')):
            command.handle_row({
                '\ufeffAPPCOM': 'LYCEE LITTRE - Desserte Etab.',
                'CODE': '10008',
                'IDARRET': '561',
                'IDCOMMUNE': '50025',
                'RAD_LON': '137913e.275',
                'RAD_LAT': '8173352.573',
                'geometry': '{"type":"Point","coordinates":[-1.35976475544314,48.6774794115165]}'
            })
            command.handle_row({
                '\ufeffAPPCOM': 'LE BOURG - COSQUEVILLE',
                'CODE': '13441',
                'IDARRET': '611',
                'IDCOMMUNE': '50142',
                'RAD_LON': '1381871.214',
                'RAD_LAT': '8286385.249',
                'geometry': '{"type":"Point","coordinates":[-1.41178715246323,49.6936332053137]}'
            })

    def test_import_maneo_stops(self):
        stop = StopPoint.objects.get(atco_code='maneo-10008')
        self.assertEqual(stop.common_name, 'Lycee Littre')
        self.assertEqual(stop.indicator, 'Desserte Etab.')
        self.assertEqual(stop.town, '')

        stop = StopPoint.objects.get(atco_code='maneo-13441')
        self.assertEqual(stop.common_name, 'Le Bourg - Cosqueville')
        self.assertEqual(stop.indicator, '')
        self.assertEqual(stop.town, 'Cosqueville')

    def test_maneo_services(self):
        services = Service.objects.order_by('service_code')
        self.assertEqual(4, len(services))
        self.assertEqual('maneo-L3', services[0].service_code)
        self.assertEqual('L3', services[0].line_name)

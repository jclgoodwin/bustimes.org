from django.test import TestCase
from ...models import StopPoint
from ..commands import import_maneo_stops

class ImportManeoTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        command = import_maneo_stops.Command()

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

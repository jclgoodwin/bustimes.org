from django.test import TestCase
from busstops.models import DataSource, Region, Operator
from ...models import Vehicle
from ..commands import import_big_change


class CambridgeImportTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Region.objects.create(id='EM', name='East Midlands')
        import_big_change.globalism['source'] = DataSource.objects.create(name='Marshalls')
        Operator.objects.create(id='MSOT', region_id='EM', name='Marshalls')

    def test_handle_data(self):
        data = {
            'resId': 13464,
            'res': 'Robbie Williams', 'assId': 35481, 'ass': 'IC115',
            'date': '2019-05-03T18:26:35Z', 'lat': 52.28732681274414, 'lng': -2.120246648788452,
            'icnR': 'res/50/h02-b-000.png', 'icnA': 'res/50/bus-b-000.png', 'dir': 346,
            'add': 'M5, Wychbold  WR9 0BS',
            'extra': {'evn': 2, 'veh': 6, 'spd': 97.7, 'dev': 10987, 'grpR': 1982, 'grpA': 1252,
                      'attrR': [], 'attrA': [], 'secR': '', 'secA': ''}
        }

        import_big_change.on_message(data)

        vehicle = Vehicle.objects.get()
        self.assertEqual(vehicle.code, 'IC115')
        self.assertEqual(vehicle.operator.name, 'Marshalls')
        self.assertIsNone(vehicle.latest_location.early)
        self.assertFalse(vehicle.latest_location.journey.destination)

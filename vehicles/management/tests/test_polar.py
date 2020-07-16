from ciso8601 import parse_datetime
from django.test import TestCase
from busstops.models import Region, Operator, DataSource
from ...models import Vehicle
from ..commands.import_polar import Command


class PolarTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        DataSource.objects.create(name='Loaches’ Coaches', url='https://loachescoaches.arcticapi.com/network/vehicles',
                                  settings={'operators': {'YCD': 'LCHS'}})

        region = Region.objects.create(id='WM')
        Operator.objects.create(id='LCHS', name='Loaches’ Coaches', region=region)

    def test_do_source(self):
        command = Command()
        with self.assertRaises(DataSource.DoesNotExist):
            command.handle('loaches')

    def test_handle_items(self):
        command = Command()
        command.source_name = 'loachescoaches'
        command.do_source()

        item = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [
                    -1.535843,
                    53.797578
                ]
            },
            "properties": {
                "direction": "outbound",
                "line": "POO",
                "vehicle": "YCD-3635",
            }
        }
        command.handle_item(item, parse_datetime('2018-08-06T22:41:15+01:00'))

        vehicle = Vehicle.objects.get()
        self.assertEqual(str(vehicle), '3635')
        self.assertEqual(str(vehicle.operator), 'Loaches’ Coaches')

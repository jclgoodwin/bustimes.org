from django.test import TestCase
from busstops.models import DataSource, Region, Operator
from ...models import Vehicle
from ..commands import import_first


class FirstImportTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.source = DataSource.objects.create(name='First')
        Region.objects.create(id='Y', name='Yorkshire')
        Operator.objects.create(id='FYOR', region_id='Y', name='Rider York')

    def test_handle_item(self):
        item = {'dir': 'inbound', 'line': '10', 'line_name': '10', 'operator': 'FYOR', 'operator_name': 'First York',
                'origin_atcocode': '2200YEA00532', 'request_time': '2020-05-16T22:49:20+01:00', 'status':
                {'bearing': 316, 'location': {'coordinates': [-1.078526, 53.957345], 'type': 'Point'},
                 'progress_between_stops': {'value': 0.773}, 'recorded_at_time': '2020-05-16T22:49:08+01:00',
                 'stops_index': {'type': 'after', 'value': 25}, 'vehicle_id': 'FYOR-inbound-2020-05-16-2225-69375-10'},
                'stops': [{'atcocode': '3290YYA01557', 'bearing': 'W', 'date': '2020-05-17', 'indicator': 'adj',
                           'latitude': 53.95546, 'locality': 'Acomb, York', 'longitude': -1.1312, 'name': 'Acomb Green',
                           'smscode': '32901557', 'stop_name': 'Acomb Green', 'time': '13:19'},
                          {'atcocode': '3290YYA00500', 'bearing': 'S', 'date': '2020-05-17', 'indicator': None,
                           'latitude': 54.04119, 'locality': 'Strensall, York', 'longitude': -1.02604,
                           'name': 'Brecks Lane', 'smscode': '32900500', 'stop_name': 'Brecks Lane', 'time': '14:15'}]}

        command = import_first.Command()
        command.source = self.source

        with self.assertNumQueries(11):
            command.handle_item(item, 'FYOR')
        with self.assertNumQueries(2):
            command.handle_item(item, 'FYOR')

        vehicle = Vehicle.objects.get(code=69375)
        self.assertEqual('FYOR', vehicle.operator_id)

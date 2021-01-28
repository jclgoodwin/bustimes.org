import vcr
import os
from mock import patch
from freezegun import freeze_time
from django.test import TestCase
from django.utils import timezone
from busstops.models import DataSource, Region, Operator, Service
from ...models import VehicleLocation
from ..commands.import_stagecoach import Command


class MockException(Exception):
    pass


DIR = os.path.dirname(os.path.abspath(__file__))


@freeze_time('2019-11-17T16:17:49.000Z')
class StagecoachTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.source = DataSource.objects.create(name='Stagecoach', datetime=timezone.now())

        r = Region.objects.create(pk='SE')
        o = Operator.objects.create(pk='SCOX', name='Oxford', parent='Stagecoach', vehicle_mode='bus', region=r)
        s = Service.objects.create(line_name='Oxford Tube', date='2019-01-01',
                                   geometry='MULTILINESTRING((-0.1475818977 51.4928233539,-0.1460401487 51.496737716))')
        s.operator.add(o)

    @patch('vehicles.management.import_live_vehicles.sleep')
    @patch('vehicles.management.commands.import_stagecoach.sleep', side_effect=MockException)
    def test_handle(self, sleep_1, sleep_2):
        command = Command()
        command.source = self.source
        command.operator_codes = ['SDVN']

        with vcr.use_cassette(os.path.join(DIR, 'vcr', 'stagecoach_vehicles.yaml')):
            with self.assertLogs(level='ERROR'):
                with self.assertNumQueries(19):
                    with patch('builtins.print'):
                        with self.assertRaises(MockException):
                            command.handle()

        self.assertTrue(sleep_1.called)
        self.assertTrue(sleep_2.called)
        self.assertEqual(command.operators, {
            'SCOX': Operator(id='SCOX'),
            'SCCM': None,
            'SCEK': None,
        })
        self.assertEqual(VehicleLocation.objects.count(), 1)

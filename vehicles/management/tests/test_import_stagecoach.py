import vcr
from mock import patch
from freezegun import freeze_time
from django.test import TestCase
from django.utils import timezone
from busstops.models import DataSource, Region, Operator, Service
from ..commands.import_stagecoach import Command


@freeze_time('2019-11-17T16:17:49.000Z')
class StagecoachTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        source = DataSource.objects.create(name='Stagecoach', datetime=timezone.now())
        cls.command = Command()
        cls.command.source = source

        r = Region.objects.create(pk='SE')
        o = Operator.objects.create(pk='SCOX', name='Oxford', parent='Stagecoach', vehicle_mode='bus', region=r)
        s = Service.objects.create(line_name='Oxford Tube', date='2019-01-01',
                                   geometry='MULTILINESTRING((-0.1475818977 51.4928233539,-0.1460401487 51.496737716))')
        s.operator.add(o)

    @patch('vehicles.management.commands.import_stagecoach.sleep')
    def test_get_items(self, sleep):
        with vcr.use_cassette('data/vcr/stagecoach_vehicles.yaml'):
            with self.assertNumQueries(2):
                items = list(self.command.get_items())
        self.assertEqual(len(items), 12)
        self.assertTrue(sleep.called)

        with self.assertNumQueries(23):
            with self.assertLogs(level='ERROR'):
                for item in items:
                    self.command.handle_item(item, self.command.source.datetime)

        with self.assertNumQueries(12):
            with self.assertLogs(level='ERROR'):
                for item in items:
                    self.command.handle_item(item, self.command.source.datetime)

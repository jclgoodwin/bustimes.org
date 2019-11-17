import vcr
from mock import patch
from freezegun import freeze_time
from django.test import TestCase
from django.utils import timezone
from busstops.models import DataSource
from ..commands.import_aircoach import Command as AircoachCommand, NatExpCommand


@freeze_time('2019-11-17T16:17:49.000Z')
class NatExpTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        source = DataSource.objects.create(name='Nathaniel Express', datetime=timezone.now())
        cls.aircoach_command = AircoachCommand()
        cls.aircoach_command.source = source
        cls.nat_exp_command = NatExpCommand()
        cls.nat_exp_command.source = source

    @patch('vehicles.management.commands.import_nx.sleep')
    def test_get_items(self, sleep):
        with vcr.use_cassette('data/vcr/nx.yaml'):
            with self.assertNumQueries(2):
                items = list(self.aircoach_command.get_items())
                self.assertEqual(len(items), 0)
                items = list(self.nat_exp_command.get_items())
                self.assertEqual(len(items), 0)
        self.assertFalse(sleep.called)

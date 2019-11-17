import vcr
from mock import patch
from freezegun import freeze_time
from django.test import TestCase
from django.utils import timezone
from busstops.models import DataSource
from ..commands.import_stagecoach import Command


@freeze_time('2019-11-17T16:17:49.000Z')
class NatExpTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        source = DataSource.objects.create(name='Stagecoach', datetime=timezone.now())
        cls.command = Command()
        cls.command.source = source

    @patch('vehicles.management.commands.import_stagecoach.sleep')
    def test_get_items(self, sleep):
        with vcr.use_cassette('data/vcr/nx.yaml'):
            with self.assertRaises(TypeError):
                items = list(self.command.get_items())
                self.assertEqual(len(items), 0)
        self.assertFalse(sleep.called)

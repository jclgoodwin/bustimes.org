import os
from unittest.mock import patch
from vcr import use_cassette
import time_machine
from django.test import TestCase, override_settings
from django.core.management import call_command
from busstops.models import Region, Operator
from ...models import Route


FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


@override_settings(PASSENGER_OPERATORS=[
    ('Unilink', 'https://www.unilinkbus.co.uk/open-data', 'SW', {
        'SQ': 'UNIL',
        'BLUS': 'BLUS',
    })
])
class ImportPassengerTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        sw = Region.objects.create(pk='SW', name='South West')
        Operator.objects.create(id='BLUS', region=sw, name='Bluestar')
        Operator.objects.create(id='UNIL', region=sw, name='Unilink')

    @time_machine.travel('2020-05-01')
    @use_cassette(os.path.join(FIXTURES_DIR, 'passenger.yaml'))
    def test_import(self):

        with patch('bustimes.management.commands.import_passenger.write_file'):
            with self.assertRaises(FileNotFoundError):
                with self.assertLogs('bustimes.management.commands.import_bod') as cm:
                    call_command('import_passenger')

        self.assertEqual(cm.output, [
            'INFO:bustimes.management.commands.import_bod:Unilink',
            "INFO:bustimes.management.commands.import_bod:{'filename': 'unilink_1586941265.zip', 'modified': True, "
            "'dates': ['2020-05-10', '2020-06-01'], 'gtfs': 'https://s3-eu-west-1.amazonaws.com/passenger-sources/u"
            "nilink/gtfs/unilink_1586941265.zip'}"
        ])

        self.assertFalse(Route.objects.all())

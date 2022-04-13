from pathlib import Path
from unittest.mock import patch
from vcr import use_cassette
from django.test import TestCase, override_settings
from django.core.management import call_command
from busstops.models import Region, Operator
from ...models import Route


@override_settings(PASSENGER_OPERATORS=[
    ('Unilink', 'unilink', 'SW', {
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

    def test_import(self):

        fixtures_dir = Path(__file__).resolve().parent / '/fixtures'

        with use_cassette(str(fixtures_dir / 'passenger.yaml'), decode_compressed_response=True):
            with patch('bustimes.management.commands.import_passenger.write_file'):
                with self.assertRaises(FileNotFoundError):
                    with self.assertLogs('bustimes.management.commands.import_bod') as cm:
                        call_command('import_passenger')

        self.assertEqual(cm.output, [
            "INFO:bustimes.management.commands.import_bod:Unilink",
            "INFO:bustimes.management.commands.import_bod:{"
            "'url': 'https://s3-eu-west-1.amazonaws.com/passenger-sources/unilink/txc/unilink_1648047602.zip', "
            "'filename': 'unilink_1648047602.zip', 'modified': True}"
        ])

        self.assertFalse(Route.objects.all())

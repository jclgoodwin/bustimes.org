import os
from mock import patch
from vcr import use_cassette
from freezegun import freeze_time
from django.test import TestCase, override_settings
from django.conf import settings
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

    @freeze_time('2020-05-01')
    @use_cassette(os.path.join(FIXTURES_DIR, 'passenger.yaml'))
    def test_import(self):

        with patch('bustimes.management.commands.import_passenger.download_if_new',
                   return_value=False) as download_if_new:
            call_command('import_passenger')

            download_if_new.assert_called_with(
                os.path.join(settings.DATA_DIR, 'unilink_1586941252.gtfs.zip'),
                'https://s3-eu-west-1.amazonaws.com/passenger-sources/unilink/gtfs/unilink_1586941252.zip'
            )

        self.assertFalse(Route.objects.all())

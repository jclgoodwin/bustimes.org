from vcr import use_cassette
from django.conf import settings
from django.core.management import call_command
from django.test import TestCase


class VehicleCodeTest(TestCase):
    def test_import_tfl(self):
        path = settings.DATA_DIR / 'vcr' / 'tfl_vehicle_code.yaml'
        with use_cassette(str(path)):
            call_command('tfl_vehicle_codes')

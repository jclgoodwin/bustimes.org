import os
from vcr import use_cassette
from django.test import TestCase, override_settings
from busstops.models import DataSource
from ...utils import flush_redis
from ...models import Vehicle, VehicleJourney
from ..commands import import_tfwm


DIR = os.path.dirname(os.path.abspath(__file__))


class TfWMImportTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        DataSource.objects.create(name="West Midlands")
        # service = Service.objects.create(line_name="44")
        # ServiceCode.objects.create(code="22498", scheme="TfWM", service=service)

    @use_cassette(os.path.join(DIR, 'vcr', 'import_tfwm.yaml'), decode_compressed_response=True)
    def test_handle(self):
        flush_redis()

        command = import_tfwm.Command()
        command.do_source()

        with override_settings(TFWM={}):
            items = command.get_items()

        self.assertEqual(218, len(items))

        with self.assertNumQueries(9):
            for item in items:
                command.handle_item(item)
            command.save()

        vehicle = Vehicle.objects.get()
        self.assertEqual(vehicle.reg, 'SN68TXN')

        with self.assertNumQueries(2):
            for item in items:
                command.handle_item(item)
            command.save()

        journey = VehicleJourney.objects.get()
        self.assertEqual(journey.route_name, "44")

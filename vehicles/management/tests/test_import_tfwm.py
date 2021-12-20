import os
import time_machine
from vcr import use_cassette
from unittest.mock import patch
from django.test import TestCase, override_settings
from ...models import Vehicle
from ..commands import import_tfwm


DIR = os.path.dirname(os.path.abspath(__file__))


class TfWMImportTest(TestCase):
    @use_cassette(os.path.join(DIR, 'vcr', 'import_tfwm.yaml'), decode_compressed_response=True)
    @time_machine.travel('2018-08-21 00:00:09')
    def test_handle(self):
        command = import_tfwm.Command()
        command.do_source()

        with override_settings(TFWM={}):
            items = command.get_items()

        # print(items)
        with self.assertNumQueries(9):
            with patch('builtins.print') as mocked_print:
                for item in items:
                    command.handle_item(item)
            mocked_print.assert_called()
            command.save()

        vehicle = Vehicle.objects.get()
        self.assertEqual(vehicle.reg, 'SN68TXN')

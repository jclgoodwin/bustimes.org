import vcr
from mock import patch
from django.test import TestCase
from ...models import Vehicle
with patch('time.sleep', return_value=None):
    from ..commands import import_hogia


def error():
    raise Exception()


class CorrectOperatorsTest(TestCase):
    @vcr.use_cassette('data/hogia.yaml')
    def test_handle(self):
        command = import_hogia.Command()

        # handle should call update
        with self.assertRaises(Exception):
            with patch('busstops.management.commands.import_hogia.Command.update', side_effect=error):
                command.handle()

        # now actually test update
        command.update()

        vehicle = Vehicle.objects.get(code='315_YN03_UVT')
        response = self.client.get(vehicle.get_absolute_url())

        self.assertContains(response, '<h1>315 YN03 UVT</h1>')

        for journey in vehicle.get_journeys():
            for location in journey:
                self.assertAlmostEqual(location.latlong.x, 1.592503)
                self.assertAlmostEqual(location.latlong.y, 52.69956)

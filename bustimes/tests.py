import os
from vcr import use_cassette
from django.test import TestCase


class BusTimesTest(TestCase):
    def test_tfl_vehicle_view(self):
        with use_cassette(
            os.path.join(
                 os.path.dirname(os.path.abspath(__file__)),
                 'vcr',
                'tfl_vehicle.yaml'
            ),
            decode_compressed_response=True
        ):
            response = self.client.get('/vehicles/tfl/LTZ1243')

            self.assertContains(response, '<h2>8 to Tottenham Court Road</h2>')
            self.assertContains(response, '<p>LTZ1243</p>')
            self.assertContains(response, '<td><a href="/stops/490010552N">Old Ford Road (OB)</a></td>')
            self.assertContains(response, '<td>18:55</td>')
            self.assertContains(response, '<td><a href="/stops/490004215M">Bow Church</a></td>')

            response = self.client.get('/vehicles/tfl/LJ53NHP')
            self.assertEqual(response.status_code, 404)

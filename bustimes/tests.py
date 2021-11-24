import os
from datetime import date, timedelta, datetime, timezone
from vcr import use_cassette
from django.test import TestCase
from busstops.models import DataSource
from vehicles.models import Livery, Vehicle
from .models import Trip


class BusTimesTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        DataSource.objects.create(id=7, name='London')
        Livery.objects.create(id=262, name='London', colours='#dc241f')

    def test_tfl_vehicle_view(self):
        with use_cassette(
            os.path.join(
                 os.path.dirname(os.path.abspath(__file__)),
                 'vcr',
                'tfl_vehicle.yaml'
            ),
            decode_compressed_response=True
        ) as cassette:
            with self.assertNumQueries(7):
                response = self.client.get('/vehicles/tfl/LTZ1243')
            # vehicle = response.context["object"]

            self.assertContains(response, '<h2>8 to Tottenham Court Road</h2>')
            self.assertContains(response, '<h2>LTZ 1243</h2>')
            self.assertContains(response, '<td class="stop-name"><a href="/stops/490010552N">Old Ford Road (OB)</a></td>')
            self.assertContains(response, '<td>18:55</td>')
            self.assertContains(response, '<td class="stop-name"><a href="/stops/490004215M">Bow Church</a></td>')

            response = self.client.get('/vehicles/tfl/LJ53NHP')
            self.assertEqual(response.status_code, 404)

            Vehicle.objects.create(code='LJ53NHP', reg='LJ53NHP')
            cassette.rewind()
            response = self.client.get('/vehicles/tfl/LJ53NHP')
            self.assertContains(response, 'LJ53 NHP')

    def test_trip(self):
        trip = Trip()

        trip.start = timedelta(hours=10, minutes=47, seconds=30)
        trip.end = timedelta(hours=11, minutes=00, seconds=00)
        self.assertEqual(
            trip.start_datetime(date(2021, 6, 20)),
            datetime(2021, 6, 20, 10, 47, 30, tzinfo=timezone(timedelta(hours=1)))
        )
        self.assertEqual(
            trip.end_datetime(date(2021, 6, 20)),
            datetime(2021, 6, 20, 11, tzinfo=timezone(timedelta(hours=1)))
        )
        self.assertEqual(
            trip.start_datetime(date(2021, 11, 1)),
            datetime(2021, 11, 1, 10, 47, 30, tzinfo=timezone(timedelta()))
        )

        trip.start = timedelta(hours=25, minutes=47, seconds=30)
        self.assertEqual(
            trip.start_datetime(date(2021, 6, 20)),
            datetime(2021, 6, 21, 1, 47, 30, tzinfo=timezone(timedelta(hours=1)))
        )
        self.assertEqual(
            trip.start_datetime(date(2021, 10, 31)),
            datetime(2021, 11, 1, 1, 47, 30, tzinfo=timezone(timedelta()))
        )

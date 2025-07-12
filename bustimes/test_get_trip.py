from datetime import datetime, timezone

from django.test import TestCase

from busstops.models import DataSource, Service
from vehicles.models import VehicleJourney
from .models import Calendar, Route, Trip


class GetTripTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        source = DataSource.objects.create(name="First Norwich")

        thursdays = Calendar.objects.create(
            start_date="2025-07-01",
            mon=True,
            tue=True,
            wed=True,
            thu=True,
            fri=False,
            sat=False,
            sun=False,
        )

        fridays = Calendar.objects.create(
            start_date="2025-07-01",
            mon=False,
            tue=False,
            wed=False,
            thu=False,
            fri=True,
            sat=False,
            sun=False,
        )
        saturdays = Calendar.objects.create(
            start_date="2025-07-01",
            mon=False,
            tue=False,
            wed=False,
            thu=False,
            fri=False,
            sat=True,
            sun=False,
        )

        cls.service = Service.objects.create(line_name="25")
        route = Route.objects.create(line_name="25", service=cls.service, source=source)

        Trip.objects.bulk_create(
            [
                Trip(
                    route=route,
                    ticket_machine_code="1111",
                    start="26:00:00",
                    end="27:00:00",
                    calendar=thursdays,
                ),
                Trip(
                    route=route,
                    ticket_machine_code="1111",
                    start="26:00:00",
                    end="27:00:00",
                    calendar=fridays,
                ),
                Trip(
                    route=route,
                    ticket_machine_code="1111",
                    start="26:00:00",
                    end="27:00:00",
                    calendar=saturdays,
                ),
            ]
        )

    def test_after_midnight(self):
        """ "It's 2am on Saturday - get_trip should get the trip with the Friday calendar"""

        journey = VehicleJourney(
            service=self.service,
            code="1111",
            datetime=datetime(2025, 7, 12, 1, 0, 0, tzinfo=timezone.utc),  # 2am BST
        )

        trip = journey.get_trip()
        self.assertTrue(trip.calendar.fri)
        self.assertFalse(trip.calendar.thu)
        self.assertFalse(trip.calendar.sat)

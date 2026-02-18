from django.test import TestCase

from busstops.models import DataSource, Service, StopPoint, StopUsage
from bustimes.models import Calendar, Route, StopTime, Trip


class ScheduledDeparturesTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        source = DataSource.objects.create(name="Henderson's Relish")

        StopPoint.objects.bulk_create(
            [
                StopPoint(atco_code="230ABCDE", active=True),
            ]
        )

        service = Service.objects.create(service_code="7", line_name="7")

        route = Route.objects.create(service=service, source=source, code="7")

        calendar = Calendar.objects.create(
            mon=True,
            tue=True,
            wed=True,
            thu=True,
            fri=True,
            sat=True,
            sun=True,
            start_date="2022-05-04",
        )

        cls.trip = Trip.objects.create(
            route=route,
            start="24:10:00",
            end="24:10:00",
            calendar=calendar,
        )
        StopTime.objects.bulk_create(
            [
                StopTime(
                    trip=cls.trip, sequence=i, stop_id="230ABCDE", departure="24:10:00"
                )
                for i in range(0, 12)
            ]
        )

        StopUsage.objects.create(service=service, stop_id="230ABCDE", order=0)

    def test_departures(self):
        with self.assertNumQueries(8):
            response = self.client.get(
                "/stops/230ABCDE/departures?date=2022-05-04&time=01:00"
            )
        print(response.text)

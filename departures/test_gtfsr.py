import vcr
from django.test import TestCase, override_settings

from busstops.models import StopPoint, Service, Operator, DataSource
from bustimes.models import Route, Trip, StopTime


class GTFSRTTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        source = DataSource.objects.create()

        StopPoint.objects.bulk_create(
            [
                StopPoint(atco_code="8220DB004962", active=True),
                StopPoint(atco_code="8220DB004725", active=True),
                StopPoint(atco_code="8220DB000408", active=True),
                StopPoint(atco_code="8220DB000412", active=True),
                StopPoint(atco_code="8220DB000416", active=True),
                StopPoint(atco_code="8220DB000418", active=True),
                StopPoint(atco_code="8220DB000420", active=True),
                StopPoint(atco_code="8220DB000421", active=True),
                StopPoint(atco_code="8220DB000424", active=True),
                StopPoint(atco_code="8250DB000427", active=True),
                StopPoint(atco_code="8250DB000429", active=True),
            ]
        )

        operator = Operator.objects.create(noc="dub", name="Dublin Bus")
        service = Service.objects.create(
            service_code="7", line_name="7", date="2022-06-01"
        )
        service.operator.add(operator)

        route = Route.objects.create(service=service, source=source, code="7")
        cls.trip = Trip.objects.create(
            route=route,
            ticket_machine_code="1767.2.60-7-b12-1.138.O",
            start="06:45:00",
            end="07:49:00",
        )
        cls.cancellable_trip = Trip.objects.create(
            route=route,
            ticket_machine_code="3966.2.60-77A-b12-1.56.I",
            start="06:45:00",
            end="07:49:00",
        )
        StopTime.objects.bulk_create(
            [
                StopTime(
                    trip=cls.trip,
                    sequence=1,
                    stop_id="8220DB004962",
                    departure="06:45:00",
                ),
                StopTime(
                    trip=cls.trip,
                    sequence=2,
                    stop_id="8220DB004725",
                    departure="06:45:00",
                ),
                StopTime(
                    trip=cls.trip,
                    sequence=5,
                    stop_id="8220DB000408",
                    departure="06:45:00",
                ),
                StopTime(
                    trip=cls.trip,
                    sequence=9,
                    stop_id="8220DB000412",
                    departure="06:45:00",
                ),
                StopTime(
                    trip=cls.trip,
                    sequence=13,
                    stop_id="8220DB000416",
                    departure="06:45:00",
                ),
                StopTime(
                    trip=cls.trip,
                    sequence=15,
                    stop_id="8220DB000418",
                    departure="06:45:00",
                ),
                StopTime(
                    trip=cls.trip,
                    sequence=17,
                    stop_id="8220DB000420",
                    departure="06:45:00",
                ),
                StopTime(
                    trip=cls.trip,
                    sequence=18,
                    stop_id="8220DB000421",
                    departure="06:45:00",
                ),
                StopTime(
                    trip=cls.trip,
                    sequence=21,
                    stop_id="8220DB000424",
                    departure="06:45:00",
                ),
                StopTime(
                    trip=cls.trip,
                    sequence=24,
                    stop_id="8250DB000427",
                    departure="06:45:00",
                ),
                StopTime(
                    trip=cls.trip,
                    sequence=26,
                    stop_id="8250DB000429",
                    departure="06:45:00",
                ),
                StopTime(
                    trip=cls.cancellable_trip,
                    sequence=1,
                    stop_id="8250DB000429",
                    departure="06:45:00",
                ),
            ]
        )

    def test_nta_ie(self):
        with override_settings(
            NTA_API_KEY="letsturn",
            CACHES={
                "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
            },
        ):
            with vcr.use_cassette("fixtures/vcr/nta_ie_trip_updates.yaml"):

                # trip with some delays
                response = self.client.get(self.trip.get_absolute_url())
                self.assertContains(response, "<td>06:47</td>")

                # cancelled trip:
                response = self.client.get(self.cancellable_trip.get_absolute_url())
                self.assertContains(response, "<p>Cancelled</p>")

                response = self.client.get("/trip_updates")
                self.assertContains(response, "1785 trip_updates")
                self.assertContains(response, "2 matching trips")

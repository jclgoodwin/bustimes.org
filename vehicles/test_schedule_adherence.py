from django.test import TestCase

from busstops.models import DataSource, StopPoint
from bustimes.models import Route, StopTime, Trip

from .models import VehicleJourney


class ScheduleAdherenceTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        StopPoint.objects.bulk_create(
            [
                StopPoint(
                    atco_code="210021503158",
                    common_name="St Peter's Street",
                    latlong="POINT(-0.336513 51.754215)",
                    active=True,
                ),
                StopPoint(
                    atco_code="210021506690",
                    common_name="Alban City School",
                    latlong="POINT(-0.334660 51.754162)",
                    active=True,
                ),
                StopPoint(
                    atco_code="210021506795",
                    common_name="St Albans City Railway Station",
                    latlong="POINT(-0.326993 51.750312)",
                    active=True,
                ),
                StopPoint(
                    atco_code="210021506765",
                    common_name="Granville Road",
                    latlong="POINT(-0.324521 51.751734)",
                    active=True,
                ),
                StopPoint(
                    atco_code="210021502200",
                    common_name="Churchill Road",
                    latlong="POINT(-0.317141 51.758903)",
                    active=True,
                ),
                StopPoint(
                    atco_code="210021502180",
                    common_name="Homewood Road",
                    latlong="POINT(-0.311548 51.759299)",
                    active=True,
                ),
                StopPoint(
                    atco_code="210021502160",
                    common_name="Beechwood Ave",
                    latlong="POINT(-0.307895 51.759714)",
                    active=True,
                ),
                StopPoint(
                    atco_code="210021509645",
                    common_name="Jersey Lane",
                    latlong="POINT(-0.307702 51.761797)",
                    active=True,
                ),
                StopPoint(
                    atco_code="210021502000",
                    common_name="The Quadrant",
                    latlong="POINT(-0.305844 51.763425)",
                    active=True,
                ),
                StopPoint(
                    atco_code="210021509680",
                    common_name="Ardens Way",
                    latlong="POINT(-0.297324 51.761854)",
                    active=True,
                ),
                StopPoint(
                    atco_code="210021509650",
                    common_name="Beechwood Ave",
                    latlong="POINT(-0.305929 51.760000)",
                    active=True,
                ),
                StopPoint(
                    atco_code="210021509620",
                    common_name="Homewood Road",
                    latlong="POINT(-0.313182 51.759376)",
                    active=True,
                ),
                StopPoint(
                    atco_code="210021509600",
                    common_name="Churchill Road",
                    latlong="POINT(-0.317167 51.759002)",
                    active=True,
                ),
                StopPoint(
                    atco_code="210021505160",
                    common_name="St Albans City Railway Station",
                    latlong="POINT(-0.326838 51.750598)",
                    active=True,
                ),
                StopPoint(
                    atco_code="210021505100",
                    common_name="Lattimore Road",
                    latlong="POINT(-0.332185 51.750952)",
                    active=True,
                ),
                StopPoint(
                    atco_code="210021505080",
                    common_name="Police Station",
                    latlong="POINT(-0.337911 51.752032)",
                    active=True,
                ),
                StopPoint(
                    atco_code="210021503160",
                    common_name="St Peter's Street",
                    latlong="POINT(-0.336842 51.753914)",
                    active=True,
                ),
            ]
        )

        source = DataSource.objects.create()

        route = Route.objects.create(source=source)

        trip = Trip.objects.create(
            route=route, start="10:30:00", end="10:54:00", destination_id="210021503158"
        )

        StopTime.objects.bulk_create(
            [
                StopTime(trip=trip, stop_id="210021503160", departure="10:30:00"),
                StopTime(trip=trip, stop_id="210021505080", departure="10:31:00"),
                StopTime(trip=trip, stop_id="210021505100", departure="10:34:00"),
                StopTime(trip=trip, stop_id="210021505160", departure="10:36:00"),
                StopTime(trip=trip, stop_id="210021509600", departure="10:39:00"),
                StopTime(trip=trip, stop_id="210021509620", departure="10:40:00"),
                StopTime(trip=trip, stop_id="210021509650", departure="10:41:00"),
                StopTime(trip=trip, stop_id="210021509680", departure="10:43:00"),
                StopTime(trip=trip, stop_id="210021502000", departure="10:45:00"),
                StopTime(trip=trip, stop_id="210021509645", departure="10:45:00"),
                StopTime(trip=trip, stop_id="210021502160", departure="10:46:00"),
                StopTime(trip=trip, stop_id="210021502180", departure="10:47:00"),
                StopTime(trip=trip, stop_id="210021502200", departure="10:48:00"),
                StopTime(trip=trip, stop_id="210021506765", departure="10:51:00"),
                StopTime(trip=trip, stop_id="210021506690", departure="10:53:00"),
                StopTime(trip=trip, stop_id="210021503158", arrival="10:54"),
            ]
        )

        cls.journey = VehicleJourney.objects.create(
            trip=trip, datetime="2022-01-04T00:00:00Z", source=source
        )

    def test(self):
        response = self.client.get(f"/journeys/{self.journey.id}.json")
        self.assertTrue(response.content)

from time import sleep, time

import ciso8601
import polyline
import requests_cache
from django.contrib.gis.geos import GEOSGeometry, LineString
from django.core.management.base import BaseCommand
from django.db import IntegrityError
from django.utils import timezone

from bustimes.models import RouteLink
from vehicles.models import VehicleJourney

from ...models import DataSource, Service


def parse_datetime(string):
    datetime = ciso8601.parse_datetime(string)
    return timezone.make_aware(datetime)


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        for trip, data in self.get_items():
            if "stops" not in data:
                continue

            if len(trip.stoptime_set.all()) == len(data["stops"]):
                self.handle_thing(trip, data)

    def service_has_missing_route_link(self, service):
        for route in service.route_set.all():
            for trip in route.trip_set.all():
                if self.trip_has_missing_route_link(trip):
                    return True
        return False

    def trip_has_missing_route_link(self, trip):
        from_stop_id = None
        for stop_time in trip.stoptime_set.all():
            to_stop_id = stop_time.stop_id
            if (
                from_stop_id
                and to_stop_id
                and (from_stop_id, to_stop_id) not in self.route_links
            ):
                return True
            from_stop_id = to_stop_id

    def get_trip(self, service, item):
        departure_time = parse_datetime(item["trip"]["departure_time_formatted_local"])
        journey = VehicleJourney(service=service)
        return journey.get_trip(departure_time=departure_time)

    def get_items(self):
        self.session = requests_cache.CachedSession(
            ignored_parameters=["api_key", "debug"]
        )

        source = DataSource.objects.get(name="Megabus")
        start = time()
        print(start)
        start = int(start) - 86400
        end = start + 86400

        for service in Service.objects.filter(operator="MEGA", current=1):
            print(service)
            self.route_links = {
                (route_link.from_stop_id, route_link.to_stop_id): route_link
                for route_link in service.routelink_set.all()
            }
            if not self.service_has_missing_route_link(service):
                print(f"{service.line_name} has all route links already")
                continue

            line_name = service.line_name
            url = source.url.format(f"{line_name}/{start}/{end}")

            response = self.session.get(url, timeout=10)
            if not response.from_cache:
                sleep(2)
            print(response.url)
            data = response.json()
            if "routes" not in data:
                print(data)
                continue
            for route in data["routes"]:
                for item in route["chronological_departures"]:
                    trip = self.get_trip(service, item)
                    if not trip:
                        continue
                    if not self.trip_has_missing_route_link(trip):
                        print(f"{trip} has all route links already")
                        continue

                    print(item)

                    direction = item["trip"]["direction"]
                    date, departure_time = item["trip"][
                        "departure_time_formatted_local"
                    ].split()
                    departure_time = departure_time.replace(":", "")[:4]
                    url = source.url.replace(
                        "-origin-departures-by-route-", "-trip-by-local-departure-time-"
                    )
                    url = url.format(
                        f"{date}/{service.line_name}/{direction}/{departure_time}"
                    )
                    response = self.session.get(url, timeout=10)
                    print(response.url)
                    yield trip, response.json()
                    if not response.from_cache:
                        sleep(2)

    def handle_thing(self, trip, data):
        route_link = None

        for i, stop_time in enumerate(trip.stoptime_set.all()):
            stop = data["stops"][i]
            latlong = GEOSGeometry(
                f"POINT({stop['wgs84_longitude_degrees']} {stop['wgs84_latitude_degrees']})"
            )
            distance = stop_time.stop.latlong.distance(latlong)
            if distance > 0.01:
                print(stop_time.stop.latlong, latlong, distance)
                break

            if route_link:
                route_link.to_stop = stop_time.stop
                try:
                    route_link.save(force_insert=True)
                except IntegrityError:
                    pass
                else:
                    self.route_links[
                        (route_link.from_stop_id, route_link.to_stop_id)
                    ] = route_link

            if not stop["geometry_to_next_stop"]:
                route_link = None

            else:
                geometry = polyline.decode(stop["geometry_to_next_stop"], geojson=True)

                route_link = RouteLink(
                    service=trip.route.service,
                    from_stop=stop_time.stop,
                    geometry=LineString(geometry).wkt,
                )

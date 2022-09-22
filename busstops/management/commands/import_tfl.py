from time import sleep

import requests_cache
from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry
from django.core.management.base import BaseCommand
from django.db import IntegrityError
from shapely import wkt
from shapely.ops import substring

from bustimes.models import RouteLink

from ...models import Service


class Command(BaseCommand):
    def get_pairs(self, sequence):
        prev_latlon = prev_stop = None

        for stop in sequence:
            latlon = wkt.loads(f"POINT({stop['lon']} {stop['lat']})")

            if prev_latlon:
                yield ((prev_stop["id"], prev_latlon), (stop["id"], latlon))

            prev_latlon = latlon
            prev_stop = stop

    def do_line(self, line_id):

        response = self.session.get(
            f"https://api.tfl.gov.uk/Line/{line_id}/Route/Sequence/all",
            params=settings.TFL
        )
        if not response.ok:
            print(line_id, response)
        from_cache = response.from_cache
        response = response.json()

        try:
            service = Service.objects.get(line_name__iexact=line_id, region="L", current=1)
        except (Service.DoesNotExist, Service.MultipleObjectsReturned) as e:
            print("⚠️", line_id, e)
            return
        print(service.slug)

        if (
            not len(response["orderedLineRoutes"])
            == len(response["lineStrings"])
            == len(response["stopPointSequences"])
        ):
            return

        existing_route_links = {
            (rl.from_stop_id, rl.to_stop_id): rl for rl in service.routelink_set.all()
        }
        to_create = {}

        for i, sequence in enumerate(response["stopPointSequences"]):
            line_string = GEOSGeometry(
                f'{{ "type": "MultiLineString", "coordinates": {response["lineStrings"][i]} }}'
            ).simplify()
            line_string = wkt.loads(line_string.wkt)

            if line_string.type != "LineString":
                continue

            pairs = list(self.get_pairs(sequence["stopPoint"]))

            for i, pair in enumerate(list(pairs)):

                from_point = pair[0][1]
                to_point = pair[1][1]

                if i == 0:
                    from_distance = 0
                else:
                    from_distance = line_string.project(from_point)

                to_distance = line_string.project(to_point)

                # print(from_distance, to_distance)

                line_substring = substring(line_string, from_distance, to_distance)

                key = pair[0][0], pair[1][0]
                if key not in existing_route_links and key not in to_create:
                    rl = RouteLink(
                        from_stop_id=pair[0][0],
                        to_stop_id=pair[1][0],
                        geometry=line_substring.wkt,
                        service=service,
                    )
                    to_create[key] = rl
                    existing_route_links[key] = rl

                # else:
                #     if existing_route_links[key].id:
                #         existing_route_links[key].geometry = line_substring.wkt
                #         existing_route_links[key].save(update_fields=["geometry"])

        try:
            RouteLink.objects.bulk_create(to_create.values())
        except (IntegrityError, TypeError) as e:
            print(e)

        if not from_cache:
            sleep(1)

    def handle(self, *args, **kwargs):
        self.session = requests_cache.CachedSession(ignored_parameters=["app_key", "app_id"])

        for route in self.session.get(
            "https://api.tfl.gov.uk/Line/Mode/bus/Route"
        ).json():
            self.do_line(route["id"])

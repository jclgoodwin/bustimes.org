from time import sleep
from itertools import pairwise

import requests
from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry
from django.core.management.base import BaseCommand
from shapely.geometry import Point
from shapely import wkt
from shapely.ops import substring

from bustimes.models import RouteLink

from ...models import Service, ServiceCode


class Command(BaseCommand):
    def get_stops(self, sequence: dict):

        for stop in sequence["stopPoint"]:
            latlon = Point(stop["lon"], stop["lat"])

            yield stop["id"], latlon

    def do_line(self, line_id):
        try:
            service = Service.objects.get(
                line_name__iexact=line_id, region="L", current=1
            )
        except (Service.DoesNotExist, Service.MultipleObjectsReturned) as e:
            print("⚠️", line_id, e)
            return
        print(service.slug)

        response = self.session.get(
            f"https://api.tfl.gov.uk/Line/{line_id}/Route/Sequence/all",
            params=settings.TFL,
        )
        if not response.ok:
            print(line_id, response)
            return

        if not service.servicecode_set.filter(scheme="TfL").exists():
            ServiceCode.objects.create(scheme="TfL", service=service, code=line_id)

        data = response.json()

        if not (
            len(data["orderedLineRoutes"])
            == len(data["lineStrings"])
            == len(data["stopPointSequences"])
        ):
            return

        to_create = {}

        for i, sequence in enumerate(data["stopPointSequences"]):
            line_string = GEOSGeometry(
                f'{{ "type": "MultiLineString", "coordinates": {data["lineStrings"][i]} }}'
            ).simplify()
            line_string = wkt.loads(line_string.wkt)

            if line_string.geom_type != "LineString":
                continue

            for j, (origin, destination) in enumerate(
                pairwise(self.get_stops(sequence))
            ):
                from_stop, from_point = origin
                to_stop, to_point = destination

                from_distance = 0 if j == 0 else line_string.project(from_point)
                to_distance = line_string.project(to_point)

                line_substring = substring(line_string, from_distance, to_distance)

                key = (from_stop, to_stop)
                if key not in to_create:
                    to_create[key] = RouteLink(
                        from_stop_id=from_stop,
                        to_stop_id=to_stop,
                        geometry=line_substring.wkt,
                        service=service,
                    )

        RouteLink.objects.bulk_create(
            to_create.values(),
            update_conflicts=True,
            update_fields=["geometry"],
            unique_fields=["service", "from_stop", "to_stop"],
        )

        sleep(1)

    def handle(self, *args, **kwargs):
        self.session = requests.Session()

        response = self.session.get(
            "https://api.tfl.gov.uk/Line/Mode/bus/Route",
            params=settings.TFL,
        ).json()

        line_names = [route["id"] for route in response]

        existing_service_codes = ServiceCode.objects.filter(
            scheme="TfL", service__current=1
        )

        service_codes_to_delete = existing_service_codes.exclude(code__in=line_names)
        print(service_codes_to_delete)

        for line_name in line_names:
            self.do_line(line_name)

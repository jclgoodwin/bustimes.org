import zipfile

from django.core.management.base import BaseCommand
from django.db import IntegrityError
from shapely.geometry import LineString, Point
from shapely.ops import substring

from bustimes.management.commands.import_gtfs import read_file
from bustimes.models import RouteLink

from ...models import Service


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("paths", nargs="+", type=str)

    def handle(self, paths, **kwargs):
        for path in paths:
            with zipfile.ZipFile(path) as archive:
                self.handle_archive(archive)

    def handle_archive(self, archive):
        self.agencies = {
            line["agency_id"]: line for line in read_file(archive, "agency.txt")
        }

        self.stops = {
            line["stop_id"]: Point(float(line["stop_lon"]), float(line["stop_lat"]))
            for line in read_file(archive, "stops.txt")
        }

        self.routes = {
            line["route_id"]: line for line in read_file(archive, "routes.txt")
        }

        self.trips = {line["trip_id"]: line for line in read_file(archive, "trips.txt")}

        shapes = {}
        for line in read_file(archive, "shapes.txt"):
            shape = (line["shape_pt_lat"], line["shape_pt_lon"])
            if line["shape_id"] in shapes:
                shapes[line["shape_id"]].append(line)
            else:
                shapes[line["shape_id"]] = [line]

        trip_id = None
        route_id = None

        for line in read_file(archive, "stop_times.txt"):
            if line["trip_id"] != trip_id:
                from_stop_id = None

                trip_id = line["trip_id"]
                # print(line)
                trip = self.trips[trip_id]

                shape_id = trip["shape_id"]
                if shape_id := trip["shape_id"]:
                    shape = shapes[shape_id]
                    line_string = LineString(
                        [
                            (
                                float(point["shape_pt_lon"]),
                                float(point["shape_pt_lat"]),
                            )
                            for point in shape
                        ]
                    )
                else:
                    shape = None
                    line_string = None

                if shape and trip["route_id"] != route_id:
                    route_id = trip["route_id"]
                    route = self.routes[route_id]

                    try:
                        service = (
                            Service.objects.filter(
                                line_name__iexact=route["route_short_name"]
                                or route["route_long_name"],
                                stops=line["stop_id"],
                                current=1,
                            )
                            .distinct()
                            .get()
                        )
                    except (
                        Service.DoesNotExist,
                        Service.MultipleObjectsReturned,
                    ) as e:
                        print(e, route["route_short_name"], line["stop_id"])
                        service = None
                    else:
                        route_links = {
                            (rl.from_stop_id, rl.to_stop_id): rl
                            for rl in service.routelink_set.all()
                        }
                        print(service)

            if service and shape:
                to_stop_id = line["stop_id"]

                if from_stop_id and (from_stop_id, to_stop_id) not in route_links:
                    from_point = self.stops[from_stop_id]
                    from_point = line_string.project(from_point)
                    to_point = self.stops[to_stop_id]
                    to_point = line_string.project(to_point)

                    line_substring = substring(line_string, from_point, to_point)

                    rl = RouteLink(
                        service=service,
                        from_stop_id=from_stop_id,
                        to_stop_id=to_stop_id,
                        geometry=line_substring.wkt,
                    )
                    if line_substring.length and from_point <= to_point:
                        try:
                            rl.save()
                        except IntegrityError as e:
                            print(e)
                            pass
                    route_links[(from_stop_id, to_stop_id)] = rl

                from_stop_id = to_stop_id

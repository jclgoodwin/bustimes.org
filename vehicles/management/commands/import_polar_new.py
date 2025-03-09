from django.contrib.gis.geos import Point
from django.db.models import Q

from busstops.models import Service

from ...models import VehicleJourney, VehicleLocation
from ..import_live_vehicles import ImportLiveVehiclesCommand
from .import_bod_avl import get_line_name_query


class Command(ImportLiveVehiclesCommand):
    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument("source_name", type=str)

    def handle(self, source_name, **options):
        self.source_name = source_name
        super().handle(**options)

    def do_source(self):
        super().do_source()
        if self.source.settings and "operators" in self.source.settings:
            self.operators = self.source.settings["operators"]
        else:
            self.operators = {}

    def get_items(self):
        return super().get_items()["features"]

    def get_operator(self, item):
        if len(self.operators) == 1:
            return list(self.operators.values())[0]
        operator = item["_embedded"]["transmodel:line"]["href"].split("/")[3]
        try:
            operator = self.operators[operator]
        except KeyError:
            if len(operator) != 4:
                return None
        return operator

    def get_vehicle(self, item):
        code = item["properties"]["vehicle"]

        if "tenant" in self.source.url and "_" in code:
            parts = code.split("_", 1)
            if parts[0].islower():
                code = parts[1]

        operator = self.get_operator(item)
        if not operator:
            return None, None

        if operator == "MCGL" and (len(code) >= 7 or len(code) >= 5 and code.isdigit()):
            # Borders Buses or First vehicles
            print(code)
            return None, None

        defaults = {"source": self.source, "operator_id": operator, "code": code}

        if "meta" in item["properties"]:
            if "number_plate" in item["properties"]["meta"]:
                defaults["reg"] = item["properties"]["meta"]["number_plate"]

        if len(code) > 4 and code[0].isalpha() and code[1] == "_":  # McGill
            defaults["fleet_code"] = code.replace("_", " ")
        elif code.isdigit():
            defaults["fleet_code"] = code

        condition = Q(operator__in=self.operators.values()) | Q(operator=operator)
        vehicles = self.vehicles.filter(condition)

        vehicle = vehicles.filter(code__iexact=code).first()

        if not vehicle and "reg" in defaults:
            vehicle = vehicles.filter(reg__iexact=defaults["reg"]).first()
            if vehicle:
                vehicle.code = code
                vehicle.save(update_fields=["code"])

        if vehicle:
            return vehicle, False

        return vehicles.get_or_create(defaults, code=code)

    def get_journey(self, item, vehicle):
        journey = VehicleJourney(
            route_name=item["properties"]["line"],
            direction=item["properties"]["direction"][:8],
            destination=item["properties"].get("destination", ""),
        )

        operator = self.get_operator(item)
        if not operator:
            return journey

        if (latest_journey := vehicle.latest_journey) and (
            latest_journey.route_name,
            latest_journey.direction,
            latest_journey.destination,
        ) == (journey.route_name, journey.direction, journey.destination):
            journey.service_id = latest_journey.service_id
        else:
            services = Service.objects.filter(
                get_line_name_query(journey.route_name), current=True, operator=operator
            )

            try:
                journey.service = self.get_service(
                    services, Point(item["geometry"]["coordinates"])
                )
            except Service.DoesNotExist:
                pass
            if not journey.service:
                print(operator, vehicle.operator_id, journey.route_name)

        return journey

    def create_vehicle_location(self, item):
        return VehicleLocation(
            latlong=Point(item["geometry"]["coordinates"]),
            heading=item["properties"].get("bearing"),
        )

    def get_items(self):
        return super().get_items()["_ajax"]["vehicles"]

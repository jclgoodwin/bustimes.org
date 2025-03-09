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
        return super().get_items()["vehicles"]  # Adjusted for /_ajax/vehicles/operator_fleet

    def get_operator(self, item):
        if len(self.operators) == 1:
            return list(self.operators.values())[0]
        operator = item.get("operator_id")  # Adjusted to match new structure
        return self.operators.get(operator, None)

    def get_vehicle(self, item):
        code = item["vehicle_id"]  # Adjusted for new format
        operator = self.get_operator(item)
        if not operator:
            return None, None

        defaults = {"source": self.source, "operator_id": operator, "code": code}

        if "meta" in item:
            if "number_plate" in item["meta"]:
                defaults["reg"] = item["meta"]["number_plate"]

        if code.isdigit():
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
            route_name=item["route_name"],
            direction=item.get("direction", "")[:8],
            destination=item.get("destination", ""),
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
                    services, Point(item["location"]["coordinates"])
                )
            except Service.DoesNotExist:
                pass
            if not journey.service:
                print(operator, vehicle.operator_id, journey.route_name)

        return journey

    def create_vehicle_location(self, item):
        return VehicleLocation(
            latlong=Point(item["location"]["coordinates"]),
            heading=item.get("bearing"),
        )

from django.contrib.gis.geos import Point
from django.db.models import Q

from busstops.models import Service, Operator

from ...models import VehicleJourney, VehicleLocation
from ..import_live_vehicles import ImportLiveVehiclesCommand
from .import_bod_avl import get_line_name_query


class Command(ImportLiveVehiclesCommand):
    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument("source_name", type=str)

    def handle(self, source_name, **options):
        self.source_name = self.vehicle_code_scheme = source_name
        super().handle(**options)

    @staticmethod
    def get_vehicle_identity(item):
        return item["properties"]["vehicle"]

    @staticmethod
    def get_journey_identity(item):
        return (
            item["properties"]["line"],
            item["properties"]["direction"],
            item["properties"].get("destination", ""),
        )

    @staticmethod
    def get_item_identity(item):
        return item["geometry"]["coordinates"]

    def get_items(self):
        return super().get_items()["features"]

    def get_vehicle(self, item):
        code = item["properties"]["vehicle"]

        # remove "{tenant}_" prefix if present
        if "tenant" in self.source.url and "_" in code:
            parts = code.split("_", 1)
            if parts[0].islower():
                code = parts[1]

        default_operator = Operator.objects.filter(
            operatorcode__source=self.source
        ).first()

        defaults = {"source": self.source, "operator": default_operator, "code": code}

        if "meta" in item["properties"]:
            if "number_plate" in item["properties"]["meta"]:
                defaults["reg"] = item["properties"]["meta"]["number_plate"]

        if len(code) > 4 and code[0].isalpha() and code[1] == "_":  # McGill
            defaults["fleet_code"] = code.replace("_", " ")
        elif code.isdigit():
            defaults["fleet_code"] = code

        vehicles = self.vehicles.filter(
            Q(operator__operatorcode__source=self.source) | Q(source=self.source)
        )
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
            direction=item["properties"]["direction"],
            destination=item["properties"].get("destination", ""),
        )

        services = Service.objects.filter(
            get_line_name_query(journey.route_name),
            current=True,
            operator__operatorcode__source=self.source,
        )

        try:
            journey.service = self.get_service(
                services, Point(item["geometry"]["coordinates"])
            )
        except Service.DoesNotExist:
            pass

        return journey

    def create_vehicle_location(self, item):
        return VehicleLocation(
            latlong=Point(item["geometry"]["coordinates"]),
            heading=item["properties"].get("bearing"),
        )

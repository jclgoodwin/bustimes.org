from datetime import timedelta, datetime
from ciso8601 import parse_datetime

from django.contrib.gis.geos import GEOSGeometry
from django.db.models import Q

from busstops.models import Operator, Service

from ...models import Vehicle, VehicleJourney, VehicleLocation
from ..import_live_vehicles import ImportLiveVehiclesCommand


def parse_date(date):
    return datetime.strptime(date, "%d.%m.%Y").date()


class Command(ImportLiveVehiclesCommand):
    source_name = "Translink"
    url = "https://vpos.translinkniplanner.co.uk/velocmap/vmi/VMI"
    previous_locations = {}

    def do_source(self):
        self.operators = Operator.objects.filter(
            noc__in=("FY", "GLE", "GDR", "MET", "ULB", "UTS")
        ).in_bulk()

        return super().do_source()

    @staticmethod
    def get_datetime(item):
        return parse_datetime(item["Timestamp"])

    def prefetch_vehicles(self, vehicle_codes):
        vehicles = self.vehicles.filter(
            operator__in=self.operators, code__in=vehicle_codes
        )
        self.vehicle_cache = {vehicle.code: vehicle for vehicle in vehicles}

    def get_items(self):
        items = []
        vehicle_codes = []

        # build list of vehicles that have moved
        for item in super().get_items():
            key = item["VehicleIdentifier"]
            value = item["Timestamp"]
            if self.previous_locations.get(key) != value:
                items.append(item)
                vehicle_codes.append(key)
                self.previous_locations[key] = value

        self.prefetch_vehicles(vehicle_codes)

        return items

    def get_vehicle(self, item) -> tuple[Vehicle, bool]:
        vehicle_code = item["VehicleIdentifier"]

        operator_id, fleet_code = vehicle_code.split("-", 1)

        if operator_id == "TM":
            operator_id = "MET"

        if vehicle_code in self.vehicle_cache:
            vehicle = self.vehicle_cache[vehicle_code]
            return vehicle, False

        vehicle = self.vehicles.filter(
            fleet_code__iexact=fleet_code,
            operator=operator_id,
        ).first()
        if not vehicle:
            vehicle = self.vehicles.filter(
                fleet_code__iexact=fleet_code,
                operator__in=self.operators,
            ).first()

        if vehicle:
            if vehicle.code != vehicle_code:
                vehicle.code = vehicle_code
                vehicle.save(update_fields=["code"])
            return vehicle, False

        vehicle = Vehicle.objects.create(
            operator_id=operator_id,
            source=self.source,
            code=vehicle_code,
            fleet_code=fleet_code,
        )
        return vehicle, True

    def get_journey(self, item, vehicle):
        journey = VehicleJourney(
            code=item["JourneyIdentifier"],
            destination=item["DirectionText"],
            route_name=item["LineText"],
        )
        if (latest_journey := vehicle.latest_journey) and (
            journey.code == latest_journey.code
            and journey.route_name == latest_journey.route_name
        ):
            return latest_journey

        journey.service = Service.objects.filter(
            Q(route__line_name__iexact=journey.route_name)
            | Q(route__line_name__iexact=f"G{journey.route_name}"),
            operator=vehicle.operator_id,
            current=True,
        ).first()
        if not journey.service:
            journey.service = Service.objects.filter(
                operator__in=self.operators,
                route__line_name__iexact=journey.route_name,
                current=True,
            ).first()

        if journey.service:
            journey.trip = journey.get_trip(date=parse_date(item["DayOfOperation"]))
            print(journey.trip)

        return journey

    def create_vehicle_location(self, item):
        delay = item.get("Delay")
        if delay is not None:
            delay = timedelta(seconds=delay)
        return VehicleLocation(
            latlong=GEOSGeometry(f"POINT({item['X']} {item['Y']})"),
            delay=delay,
        )

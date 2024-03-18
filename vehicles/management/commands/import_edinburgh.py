from datetime import datetime, timedelta, timezone

from django.contrib.gis.geos import GEOSGeometry

from busstops.models import Service
from bustimes.models import Trip

from ...models import Vehicle, VehicleJourney, VehicleLocation
from ..import_live_vehicles import ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    operators = ("LOTH", "EDTR", "ECBU", "NELB")
    source_name = "TfE"
    wait = 39
    services = Service.objects.filter(operator__in=operators, current=True).defer(
        "geometry", "search_vector"
    )
    previous_locations = {}

    def get_datetime(self, item):
        timestamp = item["last_gps_fix"]
        if item["source"] == "MyBusTracker" and item["last_gps_fix_secs"] > 3600:
            timestamp += 3600
        return datetime.fromtimestamp(timestamp, timezone.utc)

    def prefetch_vehicles(self, vehicle_codes):
        vehicles = self.vehicles.filter(source=self.source, code__in=vehicle_codes)
        self.vehicle_cache = {vehicle.code: vehicle for vehicle in vehicles}

    def get_items(self):
        items = []
        vehicle_codes = []

        # build list of vehicles that have moved
        for item in super().get_items()["vehicles"]:
            key = item["vehicle_id"].removeprefix("T")
            value = (
                item["service_name"],
                item["journey_id"],
                item["destination"],
                item["longitude"],
                item["latitude"],
                item["heading"],
            )
            if self.previous_locations.get(key) != value:
                items.append(item)
                vehicle_codes.append(key)
                self.previous_locations[key] = value

        self.prefetch_vehicles(vehicle_codes)

        return items

    def get_vehicle(self, item):
        if item["longitude"] == -7.557172 and item["latitude"] == 49.7668:
            return None, None

        vehicle_code = item["vehicle_id"].removeprefix("T")

        if vehicle_code in self.vehicle_cache:
            return self.vehicle_cache[vehicle_code], False

        vehicle = Vehicle(
            operator_id="LOTH",
            code=vehicle_code,
            source=self.source,
        )
        if vehicle_code.isdigit():
            vehicle.fleet_number = vehicle_code
        vehicle.save()

        return vehicle, True

    def get_journey(self, item, vehicle):
        journey = VehicleJourney(
            route_name=item["service_name"] or "",
            code=item["journey_id"] or "",
            destination=item["destination"] or "",
        )

        if not journey.route_name and vehicle.operator_id == "EDTR":
            journey.route_name = "T50"

        latest = vehicle.latest_journey
        if not journey.route_name:
            if latest and self.get_datetime(item) - latest.datetime < timedelta(
                hours=1
            ):
                return latest
        elif latest and latest.route_name == journey.route_name:
            if (
                latest.code == journey.code
                and latest.destination == journey.destination
            ):
                return latest
            journey.service_id = latest.service_id
        else:
            try:
                journey.service = self.services.get(
                    line_name__iexact=journey.route_name
                )
                if journey.service:
                    operator = journey.service.operator.first()
                    if not vehicle.operator_id or vehicle.operator_id != operator.noc:
                        vehicle.operator = operator
                        vehicle.save(update_fields=["operator"])

            except (Service.DoesNotExist, Service.MultipleObjectsReturned) as e:
                print(e, item["service_name"])

        if journey.service_id and journey.code:
            try:
                journey.trip = Trip.objects.get(
                    route__service=journey.service_id, ticket_machine_code=journey.code
                )
            except (Trip.DoesNotExist, Trip.MultipleObjectsReturned):
                pass

        return journey

    def create_vehicle_location(self, item):
        return VehicleLocation(
            latlong=GEOSGeometry(f"POINT({item['longitude']} {item['latitude']})"),
            heading=item["heading"] or None,
        )

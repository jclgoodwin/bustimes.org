from datetime import datetime, timezone

from django.contrib.gis.geos import GEOSGeometry

from busstops.models import Service
from bustimes.models import Trip

from ...models import VehicleJourney, VehicleLocation
from ..import_live_vehicles import ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    source_name = "TfE"
    wait = 39
    services = Service.objects.filter(
        operator__in=("LOTH", "EDTR", "ECBU", "NELB"), current=True
    ).defer("geometry", "search_vector")
    previous_locations = {}

    def get_datetime(self, item):
        timestamp = item["last_gps_fix"]
        if item["source"] == "MyBusTracker" and item["last_gps_fix_secs"] > 3600:
            timestamp += 3600
        return datetime.fromtimestamp(timestamp, timezone.utc)

    def get_items(self):
        items = super().get_items()
        return items["vehicles"]

    def get_vehicle(self, item):
        if item["longitude"] == -7.557172 and item["latitude"] == 49.7668:
            return None, None

        vehicle_defaults = {"operator_id": "LOTH"}
        vehicle_code = item["vehicle_id"]
        if vehicle_code.isdigit():
            vehicle_defaults["fleet_number"] = vehicle_code

        return self.vehicles.get_or_create(
            vehicle_defaults, source=self.source, code=vehicle_code
        )

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
            pass
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

        if journey.service and journey.code:
            try:
                journey.trip = Trip.objects.get(
                    route__service=journey.service, ticket_machine_code=journey.code
                )
            except (Trip.DoesNotExist, Trip.MultipleObjectsReturned):
                pass

        return journey

    def create_vehicle_location(self, item):
        location = VehicleLocation(
            latlong=GEOSGeometry(f"POINT({item['longitude']} {item['latitude']})"),
            heading=item["heading"] or None,
        )

        # stationary bus - ignore (?)
        key = item["vehicle_id"]
        if key in self.previous_locations:
            prev = self.previous_locations[key]
            if prev.latlong == location.latlong and prev.heading == location.heading:
                return
        self.previous_locations[key] = location

        return location

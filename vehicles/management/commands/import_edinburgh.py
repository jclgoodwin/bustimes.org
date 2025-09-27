from datetime import datetime, timedelta, timezone

from django.db.models import Q
from django.contrib.gis.geos import GEOSGeometry

from busstops.models import Service
from bustimes.models import Trip

from ...models import Vehicle, VehicleJourney, VehicleLocation
from ..import_live_vehicles import ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    operators = ("LOTH", "EDTR", "ECBU", "NELB", "ETOR")
    source_name = vehicle_code_scheme = "TfE"
    wait = 39
    services = Service.objects.filter(operator__in=operators, current=True).defer(
        "geometry", "search_vector"
    )

    @staticmethod
    def get_vehicle_identity(item):
        return item["vehicle_id"]

    @staticmethod
    def get_journey_identity(item):
        return (
            item["service_name"],
            item["journey_id"],
            item["destination"],
        )

    @staticmethod
    def get_item_identity(item):
        return (
            item["longitude"],
            item["latitude"],
        )

    @staticmethod
    def get_datetime(item):
        timestamp = item["last_gps_fix"]
        if item["source"] == "MyBusTracker" and item["last_gps_fix_secs"] > 3600:
            timestamp += 3600
        return datetime.fromtimestamp(timestamp, timezone.utc)

    def get_items(self):
        return super().get_items()["vehicles"]

    def get_vehicle(self, item):
        # somewhere in the Atlantic Ocean where real buses don't go
        if item["longitude"] == -7.557172 and item["latitude"] == 49.7668:
            return None, None

        vehicle_code = item["vehicle_id"].removeprefix("T")

        return Vehicle.objects.filter(
            Q(operator__in=self.operators) | Q(source=self.source)
        ).get_or_create(
            {"source": self.source, "operator_id": self.operators[0]},
            code=vehicle_code,
        )

    def get_journey(self, item, vehicle):
        journey = VehicleJourney(
            route_name=item["service_name"] or "",
            code=item["journey_id"] or "",
            destination=item["destination"] or "",
        )

        if not journey.route_name and vehicle.operator_id == "EDTR":
            journey.route_name = "T50"

        if latest := vehicle.latest_journey:
            time_since_latest = self.get_datetime(item) - latest.datetime

        if not item["service_name"]:
            if latest and time_since_latest < timedelta(hours=1):
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

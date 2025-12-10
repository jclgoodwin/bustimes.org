from ciso8601 import parse_datetime
from django.db.models import Q
from django.contrib.gis.geos import GEOSGeometry

from busstops.models import Service
from bustimes.models import Trip

from ...models import Vehicle, VehicleJourney, VehicleLocation
from ..import_live_vehicles import ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    operators = ("LOTH", "EDTR", "ECBU", "NELB", "ETOR")
    source_name = vehicle_code_scheme = "TfE"
    url = "https://lothianapi.com/vehicles/all"
    wait = 39
    services = Service.objects.filter(operator__in=operators, current=True).defer(
        "geometry", "search_vector"
    )

    @staticmethod
    def get_vehicle_identity(item):
        return item["vehicleID"]

    @staticmethod
    def get_journey_identity(item):
        return (
            item["routeName"],
            item["tripID"],
            item["destination"],
        )

    @staticmethod
    def get_item_identity(item):
        return (
            item["coordinate"]["longitude"],
            item["coordinate"]["latitude"],
        )

    @staticmethod
    def get_datetime(item):
        timestamp = item["lastUpdated"]
        if not timestamp:
            print(item)
            return
        if len(timestamp) == 19:
            # we don't know yet, but assume it's in UTC
            # need to revisit next British Supper Time
            timestamp += "Z"
        return parse_datetime(timestamp)

    def get_items(self):
        return super().get_items()["vehicles"]

    def get_vehicle(self, item):
        vehicle_code = item["vehicleID"]

        return Vehicle.objects.filter(
            Q(operator__in=self.operators) | Q(source=self.source)
        ).get_or_create(
            {"source": self.source, "operator_id": self.operators[0]},
            code=vehicle_code,
        )

    def get_journey(self, item, vehicle):
        journey = VehicleJourney(
            route_name=item["routeName"] or "",
            code=item["tripID"] or "",
            destination=item["destination"] or "",
        )

        # if not journey.route_name and vehicle.operator_id == "EDTR":
        #     journey.route_name = "T50"
        if journey.route_name == "Tram":
            journey.route_name = "T50"

        if (latest := vehicle.latest_journey) and (
            latest.route_name == journey.route_name
            and latest.code == journey.code
            and latest.destination == journey.destination
        ):
            return latest

        if not journey.route_name:
            return journey

        try:
            journey.service = self.services.get(line_name__iexact=journey.route_name)
        except (Service.DoesNotExist, Service.MultipleObjectsReturned) as e:
            print(e, item["routeName"], item)
        else:
            operator = journey.service.operator.first()
            if not vehicle.operator_id or vehicle.operator_id != operator.noc:
                vehicle.operator = operator
                vehicle.save(update_fields=["operator"])

        if journey.service_id and journey.code:
            try:
                journey.trip = Trip.objects.get(
                    route__service=journey.service_id, ticket_machine_code=journey.code
                )
            except (Trip.DoesNotExist, Trip.MultipleObjectsReturned):
                pass

        return journey

    def create_vehicle_location(self, item):
        coords = item["coordinate"]
        if coords["longitude"] < -7 and coords["latitude"] < 50:
            return
        return VehicleLocation(
            latlong=GEOSGeometry(f"POINT({coords['longitude']} {coords['latitude']})"),
            heading=item["bearing"] or None,
        )

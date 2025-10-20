from ciso8601 import parse_datetime
from django.contrib.gis.geos import GEOSGeometry
from django.utils.timezone import localdate
from ...models import VehicleLocation, VehicleJourney
from ..import_live_vehicles import ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    source_name = vehicle_code_scheme = "guernsey"

    def get_items(self):
        response = self.session.get(self.source.url, **self.source.settings)
        return response.json().get("items")

    @staticmethod
    def get_datetime(item):
        return parse_datetime(item["reported"])

    @staticmethod
    def get_vehicle_identity(item):
        return item["vehicleRef"]

    @staticmethod
    def get_journey_identity(item):
        return (
            item["scheduledTripStartTime"],
            item["routeName"],
            item.get("destination"),
        )

    @staticmethod
    def get_item_identity(item):
        return item["reported"]

    def get_vehicle(self, item):
        code = item["vehicleRef"]
        defaults = {"reg": code}

        return self.vehicles.get_or_create(defaults, code=code, operator_id="SGUE")

    def get_journey(self, item, vehicle):
        datetime = parse_datetime(item["scheduledTripStartTime"])

        latest_journey = vehicle.latest_journey
        if latest_journey and latest_journey.datetime == datetime:
            journey = latest_journey
        else:
            date = localdate(datetime)
            journey = vehicle.vehiclejourney_set.filter(
                date=date, datetime=datetime
            ).first()
            if not journey:
                journey = VehicleJourney(date=date, datetime=datetime)

        journey.route_name = item["routeName"]
        journey.destination = item.get("destination", "")

        return journey

    def create_vehicle_location(self, item):
        position = item["position"]
        bearing = position.get("bearing")
        if bearing == "-1":
            bearing = None
        return VehicleLocation(
            latlong=GEOSGeometry(
                f"POINT({position['longitude']} {position['latitude']})"
            ),
            heading=bearing,
        )

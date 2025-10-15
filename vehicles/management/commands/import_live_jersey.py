from ciso8601 import parse_datetime
from django.contrib.gis.geos import Point
from busstops.models import Service
from ..import_live_vehicles import ImportLiveVehiclesCommand
from ...models import VehicleLocation, VehicleJourney


class Command(ImportLiveVehiclesCommand):
    source_name = vehicle_code_scheme = "jersey"
    operator = "libertybus"
    url = "http://sojbuslivetimespublic.azurewebsites.net/api/Values?secondsAgo=360"

    @staticmethod
    def get_datetime(item):
        return parse_datetime(item["TimeOfUpdate"] + "Z")

    @staticmethod
    def get_vehicle_identity(item):
        return item["AssetRegistrationNumber"]

    @staticmethod
    def get_journey_identity(item):
        return (
            item["ServiceNumber"],
            item["OriginalStartTime"],
            item["Direction"],
        )

    @staticmethod
    def get_item_identity(item):
        return item["TimeOfUpdate"]

    def get_vehicle(self, item):
        vehicle_code = item["AssetRegistrationNumber"]
        defaults = {
            "operator_id": self.operator,
        }
        if vehicle_code.isdigit():
            defaults["fleet_number"] = vehicle_code
        else:
            defaults["reg"] = vehicle_code
        return self.vehicles.get_or_create(
            defaults, source=self.source, code=vehicle_code
        )

    def get_items(self):
        return super().get_items()["updates"]

    def get_journey(self, item, _):
        journey = VehicleJourney()
        journey.route_name = item["ServiceName"]
        journey.direction = item["Direction"]
        journey.datetime = parse_datetime(item["OriginalStartTime"] + "Z")
        journey.service = Service.objects.filter(
            line_name=journey.route_name, operator=self.operator, current=True
        ).first()
        return journey

    def create_vehicle_location(self, item):
        return VehicleLocation(
            latlong=Point(item["Longitude"], item["Latitude"]), heading=item["Bearing"]
        )

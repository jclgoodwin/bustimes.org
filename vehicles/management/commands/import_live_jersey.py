import datetime
from django.contrib.gis.geos import Point
from ..import_live_vehicles import ImportLiveVehiclesCommand
from ...models import VehicleLocation, VehicleJourney


class Command(ImportLiveVehiclesCommand):
    source_name = vehicle_code_scheme = "jersey"
    operator = "libertybus"
    url = "http://sojbuslivetimespublic.azurewebsites.net/api/Values/GetMin?secondsAgo=360"

    @staticmethod
    def get_datetime(item):
        now_datetime = datetime.datetime.now(datetime.timezone.utc)
        then_time = datetime.datetime.strptime(item["time"], "%H:%M:%S").time()

        now_time = now_datetime.time().replace(tzinfo=now_datetime.tzinfo)
        then_time = then_time.replace(tzinfo=now_datetime.tzinfo)

        if now_time < then_time:
            # yesterday
            now_datetime -= datetime.timedelta(days=1)
        return datetime.datetime.combine(now_datetime, then_time)

    @staticmethod
    def get_vehicle_identity(item):
        return item["bus"].split("-", 4)[-1]

    @staticmethod
    def get_journey_identity(item):
        return (
            item["bus"],
            item["line"],
            item["direction"],
        )

    @staticmethod
    def get_item_identity(item):
        return item["time"]

    def get_vehicle(self, item):
        parts = item["bus"].split("-", 4)
        vehicle_code = parts[-1]
        defaults = {
            "operator_id": self.operator,
        }
        if vehicle_code.isdigit():
            defaults["fleet_number"] = vehicle_code
        return self.vehicles.get_or_create(
            defaults, source=self.source, code=vehicle_code
        )

    def get_items(self):
        return super().get_items()["minimumInfoUpdates"]

    def get_journey(self, item, vehicle):
        journey = VehicleJourney()
        parts = item["bus"].split("-", 4)
        journey.code = parts[2]
        journey.route_name = item["line"]
        journey.direction = item["direction"]
        return journey

    def create_vehicle_location(self, item):
        return VehicleLocation(
            latlong=Point(item["lon"], item["lat"]), heading=item["bearing"]
        )

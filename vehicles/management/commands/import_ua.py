from ...models import Vehicle, VehicleJourney
from .import_tfwm import Command as ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    source_name = "Lviv"
    url = "http://track.ua-gis.com/gtfs/lviv/vehicle_position"

    def get_vehicle(self, item):
        return Vehicle.objects.get_or_create(
            code=item.vehicle.vehicle.id,
            reg=item.vehicle.vehicle.license_plate,
            source=self.source
        )

    def get_journey(self, item, vehicle):
        journey = VehicleJourney(
            code=item.vehicle.trip.trip_id,
            route_name=item.vehicle.trip.route_id
        )
        return journey

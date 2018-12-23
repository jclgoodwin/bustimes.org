from django.core.management.base import BaseCommand
from busstops.models import DataSource, Vehicle as OldVehicle, VehicleType as OldVehicleType
from ...models import Vehicle, VehicleType, VehicleLocation, VehicleJourney


def get_journey_code(label):
    parts = label.split()
    if len(parts) > 1:
        return parts[1]
    return ''


class Command(BaseCommand):
    def handle(self, **options):
        vehicle_types = {}
        for vehicle_type in OldVehicleType.objects.all():
            new_vehicle_type = VehicleType.objects.get_or_create(name=vehicle_type.name,
                                                                 double_decker=vehicle_type.double_decker)[0]
            vehicle_types[vehicle_type] = new_vehicle_type

        vehicles = {}
        for vehicle in OldVehicle.objects.order_by('id'):
            new_vehicle = Vehicle.objects.get_or_create(source=vehicle.source, fleet_number=vehicle.fleet_number,
                                                        reg=vehicle.reg, operator=vehicle.operator, code=vehicle.code,
                                                        vehicle_type=vehicle_types.get(vehicle.vehicle_type))[0]
            vehicles[vehicle] = new_vehicle

        source = DataSource.objects.get(name='NCC Hogia')
        for vehicle in source.vehicle_set.all():
            print(vehicle.id)
            journey = None
            new_vehicle = vehicles[vehicle]
            for location in vehicle.vehiclelocation_set.all():
                if location.data and 'Label' in location.data:
                    journey_code = get_journey_code(location.data['Label'])
                else:
                    journey_code = ''
                if not journey or journey_code != journey.code or journey.service != location.service:
                    journey = VehicleJourney.objects.create(code=journey_code, datetime=location.datetime,
                                                            vehicle=new_vehicle, service=location.service,
                                                            source=source)
                VehicleLocation.objects.create(latlong=location.latlong, datetime=location.datetime, journey=journey,
                                               early=location.early, heading=location.heading)

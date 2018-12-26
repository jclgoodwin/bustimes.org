from django.contrib.gis.geos import Point
from busstops.models import Service
from ...models import Vehicle, VehicleLocation, VehicleJourney
from ..import_live_vehicles import ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    url = 'http://tfeapp.com/live/vehicles.php'
    source_name = 'TfE'
    services = Service.objects.filter(operator__in=('LOTH', 'EDTR', 'ECBU', 'NELB'), current=True)

    def get_journey(self, item):
        journey = VehicleJourney(
            code=item['journey_id'],
            destination=item['destination']
        )

        vehicle_defaults = {}
        vehicle_code = item['vehicle_id']
        if vehicle_code.isdigit():
            vehicle_defaults['fleet_number'] = vehicle_code

        journey.vehicle, vehicle_created = Vehicle.objects.update_or_create(
            vehicle_defaults,
            source=self.source,
            code=vehicle_code
        )

        try:
            journey.service = self.services.get(line_name=item['service_name'])
        except (Service.DoesNotExist, Service.MultipleObjectsReturned) as e:
            if item['service_name'] not in {'ET1', 'MA1', '3BBT'}:
                print(e, item['service_name'])

        return journey, vehicle_created

    def create_vehicle_location(self, item, vehicle, service):
        if service and vehicle.operator != service.operator.first():
            vehicle.operator = service.operator.first()
            vehicle.save()

        return VehicleLocation(
            latlong=Point(item['longitude'], item['latitude']),
            heading=item['heading']
        )

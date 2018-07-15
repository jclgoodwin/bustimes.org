from django.contrib.gis.geos import Point
from ...models import Vehicle, VehicleLocation, Service
from ..import_live_vehicles import ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    url = 'https://tfeapp.com/live/vehicles.php'
    source_name = 'TfE'
    operators = ('LOTH', 'EDTR', 'ECBU', 'NELB')

    def get_vehicle_and_service(self, item):
        vehicle = item['vehicle_id']
        vehicle, created = Vehicle.objects.update_or_create(
            source=self.source,
            code=vehicle
        )

        try:
            service = Service.objects.get(operator__in=self.operators, line_name=item['service_name'], current=True)
        except (Service.DoesNotExist, Service.MultipleObjectsReturned) as e:
            service = None
            print(e, item['service_name'])

        return vehicle, created, service

    def create_vehicle_location(self, item, vehicle, service):
        if service and not vehicle.operator:
            vehicle.operator = service.operator.first()
            vehicle.save()

        return VehicleLocation(
            latlong=Point(item['longitude'], item['latitude']),
            heading=item['heading']
        )

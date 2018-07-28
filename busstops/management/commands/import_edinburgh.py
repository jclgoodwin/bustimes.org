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
            if item['service_name'] not in {'ET1', 'MA1', '3BBT'}:
                print(e, item['service_name'])

        return vehicle, created, service

    def create_vehicle_location(self, item, vehicle, service):
        if service and vehicle.operator != service.operator.first():
            vehicle.operator = service.operator.first()
            vehicle.save()

        return VehicleLocation(
            latlong=Point(item['longitude'], item['latitude']),
            heading=item['heading']
        )

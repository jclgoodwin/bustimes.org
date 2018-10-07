from django.contrib.gis.geos import Point
from ..import_live_vehicles import ImportLiveVehiclesCommand
from ...models import Vehicle, VehicleLocation, Service


class Command(ImportLiveVehiclesCommand):
    source_name = 'guernsey'
    operator = 'guernsey'
    url = 'http://buses.gg/zoomdata.php'

    def get_vehicle_and_service(self, item):
        code = item['name']
        if code == 'Dummy':
            return None, None, None

        defaults = {
            'operator_id': self.operator,
        }
        if '_-_' in code:
            defaults['fleet_number'], defaults['reg'] = code.split('_-_')
        vehicle, created = Vehicle.objects.get_or_create(
            defaults,
            source=self.source,
            code=code
        )

        line_name = item['line'].split('/')[-1].split('.')[0]

        try:
            service = Service.objects.get(line_name__iexact=line_name, region='GG', current=True,
                                          operator=self.operator)
        except (Service.MultipleObjectsReturned, Service.DoesNotExist) as e:
            print(e, item['line'])
            service = None

        return vehicle, created, service

    def create_vehicle_location(self, item, vehicle, service):
        position = item['position']
        latlong = Point(position['long'], position['lat'])
        return VehicleLocation(latlong=latlong)

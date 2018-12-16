from urllib.parse import unquote
from django.contrib.gis.geos import Point
from ..import_live_vehicles import ImportLiveVehiclesCommand
from ...models import Vehicle, VehicleLocation, Service


class Command(ImportLiveVehiclesCommand):
    url = 'http://ncc.hogiacloud.com/map/VehicleMapService/Vehicles'
    source_name = 'NCC Hogia'

    def get_items(self):
        for item in super().get_items():
            if item['Speed'] != item['Speed']:  # NaN
                item['Speed'] = None
            yield item

    def get_vehicle_and_service(self, item):
        label = item['Label']
        if ': ' in label:
            vehicle, service = label.split(': ', 1)
        else:
            service = None

        vehicle, vehicle_created = Vehicle.objects.update_or_create(
            source=self.source,
            code=label.split(': ')[0]
        )

        if service:
            service = service.split('/', 1)[0]
            try:
                service = Service.objects.get(servicecode__scheme=self.source_name, servicecode__code=service,
                                              current=True)
            except (Service.DoesNotExist, Service.MultipleObjectsReturned) as e:
                print(e, vehicle.operator, service)
                service = None
        else:
            service = None

        return vehicle, vehicle_created, service

    def create_vehicle_location(self, item, vehicle, service):
        label = item['Label'].split()
        if len(label) == 3:
            early = int(unquote(label[2]))
        else:
            early = None
        return VehicleLocation(
            latlong=Point(item['Longitude'], item['Latitude']),
            early=early,
            heading=item['Direction']
        )

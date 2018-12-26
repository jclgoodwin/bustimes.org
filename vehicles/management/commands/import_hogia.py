from urllib.parse import unquote
from django.contrib.gis.geos import Point
from busstops.models import Service
from ..import_live_vehicles import ImportLiveVehiclesCommand
from ...models import Vehicle, VehicleLocation, VehicleJourney


class Command(ImportLiveVehiclesCommand):
    url = 'http://ncc.hogiacloud.com/map/VehicleMapService/Vehicles'
    source_name = 'NCC Hogia'
    services = Service.objects.filter(servicecode__scheme=source_name, current=True)

    def get_items(self):
        for item in super().get_items():
            if item['Speed'] != item['Speed']:  # NaN
                item['Speed'] = None
            yield item

    def get_journey(self, item):
        journey = VehicleJourney()

        label = item['Label']
        if ': ' in label:
            vehicle, journey_code = label.split(': ', 1)
            journey.code = journey_code.split(' ', 1)[0]
            service = journey_code.split('/', 1)[0]
            try:
                journey.service = self.services.get(servicecode__code=service)
            except (Service.DoesNotExist, Service.MultipleObjectsReturned) as e:
                print(e, vehicle, service)
        else:
            vehicle = label

        journey.vehicle, vehicle_created = Vehicle.objects.update_or_create(
            source=self.source,
            code=vehicle
        )

        return journey, vehicle_created

    def create_vehicle_location(self, item, *args):
        location = VehicleLocation(
            latlong=Point(item['Longitude'], item['Latitude']),
            heading=item['Direction']
        )

        label = item['Label'].split()
        if len(label) == 3:
            location.early = int(unquote(label[2]))

        return location

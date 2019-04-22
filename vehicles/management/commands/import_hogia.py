from urllib.parse import unquote
from django.contrib.gis.geos import Point
from busstops.models import Service
from ..import_live_vehicles import ImportLiveVehiclesCommand
from ...models import Vehicle, VehicleLocation, VehicleJourney


class Command(ImportLiveVehiclesCommand):
    url = 'http://ncc.hogiacloud.com/map/VehicleMapService/Vehicles'
    source_name = 'NCC Hogia'
    services = Service.objects.filter(current=True)

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
            journey.code = journey_code.split(' ', 1)[0]  # '136/1241'
            service, journey_code = journey.code.split('/', 1)  # '136', '1241'

            try:
                journey.service = self.services.get(servicecode__scheme=self.source_name, servicecode__code=service)
                journey_code = journey.service.journeycode_set.filter(code=journey_code).first()
                if journey_code:
                    journey.destination = journey_code.destination
            except (Service.DoesNotExist, Service.MultipleObjectsReturned) as e:
                print(e, item)

        else:
            vehicle = label

        journey.vehicle, vehicle_created = Vehicle.objects.update_or_create(
            source=self.source,
            code=vehicle
        )

        if not journey.service_id and journey.vehicle.operator_id:
            services = self.services.filter(operator=journey.vehicle.operator_id)
            latlong = Point(item['Longitude'], item['Latitude'])
            try:
                journey.service = self.get_service(services, latlong)
            except (Service.DoesNotExist, Service.MultipleObjectsReturned):
                pass

        return journey, vehicle_created

    def create_vehicle_location(self, item):
        location = VehicleLocation(
            latlong=Point(item['Longitude'], item['Latitude']),
            heading=item['Direction']
        )

        label = item['Label'].split()
        if len(label) == 3:
            location.early = int(unquote(label[2]).replace('±', ''))

        return location

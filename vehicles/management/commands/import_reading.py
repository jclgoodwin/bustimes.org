from ciso8601 import parse_datetime
from django.utils.timezone import make_aware
from django.contrib.gis.geos import Point
from busstops.models import Service
from ...models import VehicleLocation, VehicleJourney
from ..import_live_vehicles import ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    url = 'http://rtl2.ods-live.co.uk/api/vehiclePositions'
    source_name = 'Reading'
    services = Service.objects.filter(operator__in=('RBUS', 'GLRB', 'KENN', 'NADS', 'THVB'), current=True)

    @staticmethod
    def get_datetime(item):
        return make_aware(parse_datetime(item['observed']))

    def get_vehicle(self, item):
        vehicle = item['vehicle']
        defaults = {
            'source': self.source
        }
        if vehicle.isdigit():
            defaults['fleet_number'] = vehicle
        return self.vehicles.get_or_create(
            defaults,
            operator_id='RBUS',
            code=vehicle
        )

    def get_journey(self, item, vehicle):
        journey = VehicleJourney()
        journey.route_name = item['service']

        if vehicle.latest_location and vehicle.latest_location.journey.route_name == journey.route_name:
            journey.service = vehicle.latest_location.journey.service
        else:
            try:
                journey.service = self.services.get(line_name=item['service'])
            except (Service.DoesNotExist, Service.MultipleObjectsReturned) as e:
                print(e, item['service'])

        return journey

    def create_vehicle_location(self, item):
        return VehicleLocation(
            latlong=Point(float(item['longitude']), float(item['latitude'])),
            heading=item['bearing'] or None
        )

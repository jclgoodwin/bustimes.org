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

        latest_journey = vehicle.latest_location and vehicle.latest_location.journey
        if latest_journey and latest_journey.service and latest_journey.route_name == journey.route_name:
            journey.service = latest_journey.service
        elif journey.route_name:
            try:
                journey.service = self.get_service(
                    self.services.filter(line_name__iexact=journey.route_name),
                    Point(float(item['longitude']), float(item['latitude']))
                )
            except Service.DoesNotExist:
                pass

            if not journey.service:
                print(item)

        return journey

    def create_vehicle_location(self, item):
        return VehicleLocation(
            latlong=Point(float(item['longitude']), float(item['latitude'])),
            heading=item['bearing'] or None
        )

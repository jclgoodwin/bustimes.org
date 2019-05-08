from datetime import datetime
from django.utils.timezone import make_aware
from django.contrib.gis.geos import Point
from busstops.models import Service
from ...models import Vehicle, VehicleLocation, VehicleJourney
from ..import_live_vehicles import ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    url = 'http://tfe-opendata.com/api/v1/vehicle_locations'
    source_name = 'TfE'
    services = Service.objects.filter(operator__in=('LOTH', 'EDTR', 'ECBU', 'NELB'), current=True)

    @staticmethod
    def get_datetime(item):
        return make_aware(datetime.utcfromtimestamp(item['last_gps_fix']))

    def get_items(self):
        items = super().get_items()
        if items:
            return (item for item in items['vehicles'] if item['service_name'])

    def get_vehicle(self, item):
        vehicle_defaults = {}
        vehicle_code = item['vehicle_id']
        if vehicle_code.isdigit():
            vehicle_defaults['fleet_number'] = vehicle_code

        return Vehicle.objects.select_related('latest_location').get_or_create(
            vehicle_defaults,
            source=self.source,
            code=vehicle_code
        )

    def get_journey(self, item, vehicle):
        journey = VehicleJourney(
            code=item['journey_id'] or '',
            destination=item['destination'] or ''
        )

        journey.route_name = item['service_name']

        try:
            journey.service = self.services.get(line_name=item['service_name'])
            if not vehicle.operator:
                vehicle.operator = journey.service.operator.first()
                vehicle.save()
        except (Service.DoesNotExist, Service.MultipleObjectsReturned) as e:
            if item['service_name'] not in {'ET1', 'MA1', '3BBT', 'C134'}:
                print(e, item['service_name'])

        return journey

    def create_vehicle_location(self, item):
        return VehicleLocation(
            latlong=Point(item['longitude'], item['latitude']),
            heading=item['heading']
        )

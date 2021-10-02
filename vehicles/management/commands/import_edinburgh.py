from datetime import datetime
from django.utils import timezone
from django.contrib.gis.geos import Point
from busstops.models import Service
from ...models import VehicleLocation, VehicleJourney
from ..import_live_vehicles import ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    url = 'http://tfe-opendata.com/api/v1/vehicle_locations'
    source_name = 'TfE'
    services = Service.objects.filter(
        operator__in=('LOTH', 'EDTR', 'ECBU', 'NELB'),
        current=True
    ).defer('geometry', 'search_vector')

    @staticmethod
    def get_datetime(item):
        return datetime.fromtimestamp(item['last_gps_fix'], timezone.utc)

    def get_items(self):
        items = super().get_items()
        return items['vehicles']

    def get_vehicle(self, item):
        if item['longitude'] == -7.557172 and item['latitude'] == 49.7668:
            return None, None

        vehicle_defaults = {
            'operator_id': 'LOTH'
        }
        vehicle_code = item['vehicle_id']
        if vehicle_code.isdigit():
            vehicle_defaults['fleet_number'] = vehicle_code

        return self.vehicles.get_or_create(
            vehicle_defaults,
            source=self.source,
            code=vehicle_code
        )

    def get_journey(self, item, vehicle):
        journey = VehicleJourney(
            code=item['journey_id'] or '',
            destination=item['destination'] or ''
        )

        journey.route_name = item['service_name'] or ''

        if not journey.route_name:
            pass
        elif vehicle.latest_journey and vehicle.latest_journey.route_name == journey.route_name:
            journey.service_id = vehicle.latest_journey.service_id
        else:
            try:
                journey.service = self.services.get(line_name__iexact=journey.route_name)
                if journey.service:
                    operator = journey.service.operator.first()
                    if not vehicle.operator_id or vehicle.operator_id != operator.id:
                        vehicle.operator = operator
                        vehicle.save(update_fields=['operator'])
            except (Service.DoesNotExist, Service.MultipleObjectsReturned) as e:
                print(e, item['service_name'])

        return journey

    def create_vehicle_location(self, item):
        return VehicleLocation(
            latlong=Point(item['longitude'], item['latitude']),
            heading=item['heading']
        )

import pytz
import ciso8601
from django.contrib.gis.geos import Point
from ..import_live_vehicles import ImportLiveVehiclesCommand
from ...models import Vehicle, VehicleLocation, Service


LOCAL_TIMEZONE = pytz.timezone('Europe/London')


class Command(ImportLiveVehiclesCommand):
    url = 'http://rtl2.ods-live.co.uk/api/vehiclePositions'
    source_name = 'Reading'

    def get_vehicle_and_service(self, item):
        service = item['service'].lower()
        operator = 'RBUS'
        if service.startswith('tv'):
            operator = 'THVB'
            service = service[2:]
        elif service.startswith('k'):
            if service != 'k102':
                operator = 'KENN'
            service = service[1:]
        elif service == '702' or service == '703':
            operator = 'GLRB'

        vehicle = item['vehicle']
        vehicle, created = Vehicle.objects.update_or_create(
            {'operator_id': operator},
            source=self.source,
            code=vehicle
        )

        if service:
            try:
                service = vehicle.operator.service_set.get(current=True, line_name__iexact=service)
            except Service.DoesNotExist:
                service = None
        else:
            service = None

        return vehicle, created, service

    def create_vehicle_location(self, item, vehicle, service):
        return VehicleLocation(
            datetime=ciso8601.parse_datetime(item['observed']).astimezone(LOCAL_TIMEZONE),
            latlong=Point(float(item['longitude']), float(item['latitude'])),
            heading=item['bearing'] or None
        )

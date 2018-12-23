import pytz
from datetime import datetime
from django.contrib.gis.geos import Point
from busstops.models import Operator, Service
from ...models import Vehicle, VehicleLocation
from ..import_live_vehicles import ImportLiveVehiclesCommand


LOCAL_TIMEZONE = pytz.timezone('Europe/London')


class Command(ImportLiveVehiclesCommand):
    source_name = 'BusHub'
    url = 'http://portal.diamondbuses.com/api/buses/nearby?latitude&longitude'

    def get_vehicle_and_service(self, item):
        operator = Operator.objects.get(id=item['OperatorRef'])
        try:
            service = operator.service_set.get(current=True, line_name=item['PublishedLineName'])
        except (Service.MultipleObjectsReturned, Service.DoesNotExist) as e:
            print(e, operator, item['PublishedLineName'], item['DestinationRef'])
            service = None

        code = item['VehicleRef']
        if code.isdigit():
            fleet_number = code
        else:
            fleet_number = None

        vehicle, created = Vehicle.objects.get_or_create(
            {'operator': operator, 'fleet_number': fleet_number},
            source=self.source,
            code=code
        )

        return vehicle, created, service

    def create_vehicle_location(self, item, vehicle, service):
        when = datetime.strptime(item['RecordedAtTime'], '%d/%m/%Y %H:%M:%S')
        when = LOCAL_TIMEZONE.localize(when)
        bearing = item['Bearing']
        if bearing == '-1':
            bearing = None
        return VehicleLocation(
            datetime=when,
            latlong=Point(float(item['Longitude']), float(item['Latitude'])),
            heading=bearing
        )

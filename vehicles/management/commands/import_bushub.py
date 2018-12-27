import pytz
from datetime import datetime
from django.contrib.gis.geos import Point
from busstops.models import Operator, Service
from ...models import Vehicle, VehicleLocation, VehicleJourney
from ..import_live_vehicles import ImportLiveVehiclesCommand


LOCAL_TIMEZONE = pytz.timezone('Europe/London')


class Command(ImportLiveVehiclesCommand):
    source_name = 'BusHub'
    url = 'http://portal.diamondbuses.com/api/buses/nearby?latitude&longitude'

    def get_journey(self, item):
        journey = VehicleJourney()

        operator = Operator.objects.get(id=item['OperatorRef'])
        try:
            journey.service = operator.service_set.get(current=True, line_name=item['PublishedLineName'])
        except (Service.MultipleObjectsReturned, Service.DoesNotExist) as e:
            print(e, operator, item['PublishedLineName'], item['DestinationRef'])

        journey.code = item['JourneyCode']
        journey.destination = item['DestinationStopLocality']

        code = item['VehicleRef']
        if code.isdigit():
            fleet_number = code
        else:
            fleet_number = None

        journey.vehicle, vehicle_created = Vehicle.objects.get_or_create(
            {'operator': operator, 'fleet_number': fleet_number},
            source=self.source,
            code=code
        )

        return journey, vehicle_created

    def create_vehicle_location(self, item):
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

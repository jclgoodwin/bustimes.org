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

    @classmethod
    def get_service(cls, operator, item):
        line_name = item['PublishedLineName']
        services = operator.service_set.filter(current=True, line_name=line_name)
        try:
            return services.get()
        except Service.DoesNotExist as e:
            if line_name[-1].isalpha():
                item['PublishedLineName'] = line_name[:-1]
            elif line_name[0].isalpha():
                item['PublishedLineName'] = line_name[1:]
            else:
                print(e, operator, line_name)
                return
            return cls.get_service(operator, item)
        except Service.MultipleObjectsReturned:
            try:
                return services.filter(stops=item['DestinationRef']).distinct().get()
            except (Service.DoesNotExist, Service.MultipleObjectsReturned) as e:
                print(e, operator, item['PublishedLineName'], item['DestinationRef'])

    def get_journey(self, item):
        journey = VehicleJourney()

        operator = Operator.objects.get(id=item['OperatorRef'])
        journey.service = self.get_service(operator, item)

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

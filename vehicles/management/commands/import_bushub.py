from datetime import datetime
from ciso8601 import parse_datetime
from django.utils import timezone
from django.contrib.gis.geos import Point
from busstops.models import Service
from ...models import Vehicle, VehicleLocation, VehicleJourney
from ..import_live_vehicles import ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    source_name = 'BusHub'
    url = 'http://portal.diamondbuses.com/api/buses/nearby?latitude&longitude'

    @staticmethod
    def get_datetime(item):
        try:
            return parse_datetime(item['RecordedAtTime'])
        except ValueError:
            return timezone.make_aware(datetime.strptime(item['RecordedAtTime'], '%d/%m/%Y %H:%M:%S'))

    def get_vehicle(self, item):
        code = item['VehicleRef']
        if code.isdigit():
            fleet_number = code
        else:
            fleet_number = None

        operators = ['NXHH', 'WNGS']
        if item['OperatorRef'] not in operators:
            operators = [item['OperatorRef']]

        return Vehicle.objects.select_related('latest_location__journey__service').get_or_create(
            {'fleet_number': fleet_number, 'source': self.source, 'operator_id': item['OperatorRef']},
            code=code,
            operator__in=operators
        )

    @classmethod
    def get_service(cls, item):
        line_name = item['PublishedLineName']
        services = Service.objects.filter(operator=item['OperatorRef'], current=True, line_name=line_name)
        try:
            return services.get()
        except Service.DoesNotExist as e:
            if line_name[-1].isalpha():
                item['PublishedLineName'] = line_name[:-1]
            elif line_name[0].isalpha():
                item['PublishedLineName'] = line_name[1:]
            else:
                print(e, item['OperatorRef'], line_name)
                return
            return cls.get_service(item)
        except Service.MultipleObjectsReturned:
            try:
                return services.filter(stops__locality__stoppoint=item['DestinationRef']).distinct().get()
            except (Service.DoesNotExist, Service.MultipleObjectsReturned) as e:
                print(e, item['OperatorRef'], item['PublishedLineName'], item['DestinationRef'])

    def get_journey(self, item, vehicle):
        journey = VehicleJourney()

        journey.route_name = item['PublishedLineName']
        journey.code = item['JourneyCode']
        if vehicle.latest_location and vehicle.latest_location.journey.code == journey.code and (
                                       vehicle.latest_location.journey.route_name == journey.route_name
        ):
            journey.service = vehicle.latest_location.journey.service
        elif item['PublishedLineName']:
            journey.service = self.get_service(item)

        journey.destination = item['DestinationStopLocality']

        return journey

    def create_vehicle_location(self, item):
        bearing = item['Bearing']
        if bearing == '-1':
            bearing = None
        return VehicleLocation(
            latlong=Point(float(item['Longitude']), float(item['Latitude'])),
            heading=bearing
        )

from datetime import datetime
from ciso8601 import parse_datetime
from django.utils import timezone
from django.contrib.gis.geos import Point
from busstops.models import Service
from ...models import VehicleLocation, VehicleJourney
from ..import_live_vehicles import ImportLiveVehiclesCommand


def get_datetime(string):
    if string:
        try:
            when = parse_datetime(string)
        except ValueError:
            when = datetime.strptime(string, '%d/%m/%Y %H:%M:%S')
        try:
            return timezone.make_aware(when)
        except ValueError:
            return when


class Command(ImportLiveVehiclesCommand):
    @staticmethod
    def add_arguments(parser):
        parser.add_argument('source_name', type=str)

    def handle(self, source_name, **options):
        self.source_name = source_name
        super().handle(**options)

    @staticmethod
    def get_datetime(item):
        return get_datetime(item['RecordedAtTime'])

    def get_vehicle(self, item):
        code = item['VehicleRef']
        if code.isdigit():
            fleet_number = code
        else:
            fleet_number = None

        if self.source.settings and 'OperatorRef' in self.source.settings:
            item['OperatorRef'] = self.source.settings['OperatorRef']

        defaults = {'fleet_number': fleet_number, 'source': self.source, 'operator_id': item['OperatorRef']}

        if item['OperatorRef'] in {'NXHH', 'WNGS', 'GTRI', 'DIAM', 'PBLT'}:
            return self.vehicles.get_or_create(defaults, code=code, operator__parent='Rotala')

        if item['OperatorRef'] == 'SESX':
            operators = ['SESX', 'NIBS', 'GECL']
        else:
            operators = [item['OperatorRef']]

        return self.vehicles.get_or_create(defaults, code=code, operator__in=operators)

    @classmethod
    def get_service(cls, item):
        line_name = item['PublishedLineName']
        if not line_name:
            return
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
        journey.datetime = get_datetime(item['DepartureTime'])
        latest_location = vehicle.latest_location
        if (
            latest_location and latest_location.journey.code == journey.code and
            latest_location.journey.route_name == journey.route_name and latest_location.journey.service
        ):
            journey.service = latest_location.journey.service
        else:
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

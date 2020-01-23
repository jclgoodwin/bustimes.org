from google.transit import gtfs_realtime_pb2
from datetime import datetime
from django.contrib.gis.geos import Point
from django.conf import settings
from django.utils import timezone
from multigtfs.models import Trip
from busstops.models import Service
from ...models import Vehicle, VehicleLocation, VehicleJourney
from ..import_live_vehicles import ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    source_name = 'TfWM'
    url = 'http://api.tfwm.org.uk/gtfs/vehicle_positions'
    routes = {}
    landflight = set()
    select_bus_services = set()

    @staticmethod
    def get_datetime(item):
        return timezone.make_aware(datetime.fromtimestamp(item.vehicle.timestamp))

    def get_items(self):
        if not self.routes:
            response = self.session.get('http://api.tfwm.org.uk/line/route', params={**settings.TFWM,
                                                                                     'formatter': 'json'}, timeout=10)
            for route in response.json()['ArrayOfLine']['Line']:
                self.routes[route['Id']] = route
                if route['Operators']['Operator'][0]['Name'] == 'Select Bus Services':
                    self.select_bus_services.add(route['Name'])
                if route['Operators']['Operator'][0]['Name'] == 'LandFlight':
                    self.landflight.add(route['Name'])

        response = self.session.get(self.url, params=settings.TFWM, timeout=10)
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(response.content)
        return feed.entity

    def get_vehicle(self, item):
        vehicle_code = item.vehicle.vehicle.id

        defaults = {
            'source': self.source
        }

        if item.vehicle.HasField('trip'):
            route = self.routes.get(item.vehicle.trip.route_id)
            if route:
                operator = route['Operators']['Operator'][0]['Name']
                if operator == 'Midland Classic' or operator == 'Diamond Bus':
                    return None, None

                vehicle_code = vehicle_code[:-len(route['Name'])]
                if operator == 'Select Bus Services':
                    operator = 'SLBS'
                elif operator == 'First Worcestershire':
                    operator = 'FSMR'
                else:
                    print(item, vehicle_code, operator)
                    return None, None

                if vehicle_code.isdigit():
                    defaults['fleet_number'] = vehicle_code

                return self.vehicles.get_or_create(defaults, operator_id=operator, code=vehicle_code)

        if len(vehicle_code) > 5 and vehicle_code[:5].isdigit():
            vehicle_code = vehicle_code[:5]
            defaults['fleet_number'] = vehicle_code
            try:
                vehicle, created = self.vehicles.get_or_create(defaults, operator__in=['DIAM', 'FSMR'],
                                                               code=vehicle_code)
                if not vehicle.operator_id:
                    print(item)
                if vehicle.operator_id == 'DIAM':
                    return None, None
                return vehicle, created
            except Vehicle.MultipleObjectsReturned as e:
                print(e)

        elif vehicle_code.startswith('BUS_'):
            for line_name in self.select_bus_services:
                if vehicle_code.endswith(line_name) and not vehicle_code.endswith('_' + line_name):
                    vehicle_code = vehicle_code[:-len(line_name)]
                    defaults['fleet_number'] = vehicle_code.split('_')[-1]
                    return self.vehicles.get_or_create(defaults, operator_id='SLBS', code=vehicle_code)

        elif vehicle_code.startswith('Y'):
            for line_name in self.landflight:
                if vehicle_code.lower().endswith(line_name.lower()):
                    vehicle_code = vehicle_code[:-len(line_name)]
                    return self.vehicles.get_or_create(defaults, operator_id='SLVL', code=vehicle_code)

        print(vehicle_code, item)
        return None, None

    def get_journey(self, item, vehicle):
        journey = VehicleJourney()

        if item.vehicle.HasField('trip'):
            if vehicle.latest_location and vehicle.latest_location.journey.code == item.vehicle.trip.trip_id:
                return vehicle.latest_location.journey

            journey.code = item.vehicle.trip.trip_id
            journey.datetime = timezone.make_aware(
                datetime.strptime(item.vehicle.trip.start_date + item.vehicle.trip.start_time, '%Y%m%d%H:%M:%S')
            )
            trips = Trip.objects.filter(route__feed__name='tfwm', trip_id=journey.code)
            trip = trips.first()
            if trip:
                journey.destination = trip.headsign

        vehicle_code = item.vehicle.vehicle.id
        if vehicle_code.startswith(vehicle.code) and len(vehicle.code) < len(vehicle_code):
            journey.route_name = vehicle_code[len(vehicle.code):]

        if item.vehicle.HasField('trip'):
            route = self.routes.get(item.vehicle.trip.route_id)
            if route:
                journey.route_name = route['Name']

        if vehicle.operator_id:
            try:
                journey.service = Service.objects.get(current=True, line_name__iexact=journey.route_name,
                                                      operator=vehicle.operator_id)
            except (Service.MultipleObjectsReturned, Service.DoesNotExist) as e:
                print(e, vehicle.operator_id, vehicle, journey.route_name)

        return journey

    def create_vehicle_location(self, item):
        return VehicleLocation(
            latlong=Point(item.vehicle.position.longitude, item.vehicle.position.latitude)
        )

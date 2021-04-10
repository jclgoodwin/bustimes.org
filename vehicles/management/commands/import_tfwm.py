from google.transit import gtfs_realtime_pb2
from datetime import datetime
from django.contrib.gis.geos import Point
from django.utils import timezone
from busstops.models import Service
from ...models import Vehicle, VehicleLocation, VehicleJourney, JourneyCode
from ..import_live_vehicles import ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    source_name = 'TfWM'
    url = 'http://api.tfwm.org.uk/gtfs/vehicle_positions'

    @staticmethod
    def get_datetime(item):
        return timezone.make_aware(datetime.fromtimestamp(item.vehicle.timestamp))

    def get_items(self):
        response = self.session.get(self.url, params=self.source.settings, timeout=10)
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(response.content)
        return feed.entity

    def get_vehicle(self, item):
        vehicle_code = item.vehicle.vehicle.id

        defaults = {
            'source': self.source
        }

        if len(vehicle_code) > 5 and vehicle_code[:5].isdigit():
            # First or Diamond Bus - defer to BODS
            return None, None

        elif vehicle_code.startswith('BUS_'):
            # Select Bus Services - defer to BODS
            return None, None

        elif vehicle_code[-3:] == 'X12':
            # Midland Classic - defer to BODS
            return None, None

        if item.vehicle.HasField('trip'):
            try:
                service = Service.objects.get(current=True, servicecode__scheme='TfWM',
                                              servicecode__code=item.vehicle.trip.route_id)
                operator = service.operator.first()

                vehicle_code = vehicle_code[:-len(service.line_name)]
                if operator:
                    if operator.name == 'Diamond Bus':
                        return None, None

                    if vehicle_code.isdigit():
                        defaults['fleet_number'] = vehicle_code

                    return self.vehicles.get_or_create(defaults, operator=operator, code=vehicle_code)
            except Service.DoesNotExist as e:
                print(e, item.vehicle.trip.route_id, vehicle_code)
                pass

        reg = vehicle_code.replace('_', '')

        if len(reg) > 7:
            route = reg[7:]
            reg = reg[:7]
            defaults['reg'] = reg
            vehicle_code = vehicle_code[:-len(route)]

        try:
            return self.vehicles.get_or_create(defaults, code=vehicle_code)
        except Vehicle.MultipleObjectsReturned:
            print(vehicle_code, item)
            return self.vehicles.filter(code=vehicle_code).first(), False

    def get_journey(self, item, vehicle):
        journey = VehicleJourney()

        if item.vehicle.HasField('trip'):
            journey.datetime = timezone.make_aware(
                datetime.strptime(item.vehicle.trip.start_date + item.vehicle.trip.start_time, '%Y%m%d%H:%M:%S')
            )

            if vehicle.latest_journey and vehicle.latest_journey.datetime == journey.datetime:
                return vehicle.latest_journey

            try:
                journey = vehicle.vehiclejourney_set.get(datetime=journey.datetime)
            except (VehicleJourney.DoesNotExist, VehicleJourney.MultipleObjectsReturned):
                pass

            journey.code = item.vehicle.trip.trip_id

            journey_code = JourneyCode.objects.filter(data_source=self.source, code=journey.code).first()
            if journey_code:
                journey.destination = journey_code.destination
                journey.service = journey_code.service

        vehicle_code = item.vehicle.vehicle.id
        if vehicle_code.startswith(vehicle.code) and len(vehicle.code) < len(vehicle_code):
            journey.route_name = vehicle_code[len(vehicle.code):]

            if vehicle.operator_id and not journey.service:
                services = Service.objects.filter(current=True, line_name__iexact=journey.route_name,
                                                  operator=vehicle.operator_id)
                if services:
                    journey.route_name = services[0].line_name
                    if len(services) == 1:
                        journey.service = services[0]

        return journey

    def create_vehicle_location(self, item):
        return VehicleLocation(
            latlong=Point(item.vehicle.position.longitude, item.vehicle.position.latitude)
        )

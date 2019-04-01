from google.transit import gtfs_realtime_pb2
from datetime import datetime
from django.contrib.gis.geos import Point
from django.conf import settings
from django.utils import timezone
from multigtfs.models import Trip
from busstops.models import Operator, Service
from ...models import Vehicle, VehicleLocation, VehicleJourney
from ..import_live_vehicles import ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    source_name = 'TfWM'
    url = 'http://api.tfwm.org.uk/gtfs/vehicle_positions'

    def get_items(self):
        response = self.session.get(self.source.url, params=settings.TFWM, timeout=10)
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(response.content)
        return feed.entity

    def get_journey(self, item):
        journey = VehicleJourney()
        operator = None
        vehicle_code = item.vehicle.vehicle.id

        trip = None
        if item.vehicle.HasField('trip'):
            journey.code = item.vehicle.trip.trip_id
            journey.datetime = timezone.make_aware(
                datetime.strptime(item.vehicle.trip.start_date + item.vehicle.trip.start_time, '%Y%m%d%H:%M:%S')
            )
            try:
                trip = Trip.objects.get(route__feed__name='tfwm', trip_id=journey.code)
            except Trip.DoesNotExist:
                print(journey.code)
                pass
            if trip:
                journey.destination = trip.headsign
                route = trip.route
                journey.route_name = route.short_name
                if route.agency.name == 'Claribel Coaches':
                    print(item)
                    operator = Operator.objects.get(name='Diamond Bus')
                else:
                    operator = Operator.objects.get(name=route.agency.name)
                try:
                    journey.service = operator.service_set.get(line_name=route.short_name, current=True)
                except Service.MultipleObjectsReturned as e:
                    print(e, operator, route.short_name)

                if vehicle_code.endswith(route.short_name):
                    vehicle_code = vehicle_code[:-len(route.short_name)]

                journey.vehicle, vehicle_created = Vehicle.objects.get_or_create({
                    'source': self.source
                }, operator=operator, code=vehicle_code)

                return journey, vehicle_created

        if len(vehicle_code) > 5 and vehicle_code[:5].isdigit():
            # route = vehicle_code[5:]
            vehicle_code = vehicle_code[:5]

            try:
                journey.vehicle, vehicle_created = Vehicle.objects.get_or_create({
                    'source': self.source
                }, operator__in=('DIAM', 'FSMR'), code=vehicle_code)

                return journey, vehicle_created
            except Vehicle.MultipleObjectsReturned:
                pass
        elif vehicle_code.startswith('BUS_'):
            operator = 'SLBS'
            for service in Service.objects.filter(operator='SLBS', current=True).order_by('-line_name'):
                if vehicle_code.endswith(service.line_name) and not vehicle_code.endswith('_' + service.line_name):
                    vehicle_code = vehicle_code[:-len(service.line_name)]
                    journey.service = service
                    break
        else:
            for service in Service.objects.filter(operator='MDCL', current=True).order_by('-line_name'):
                if vehicle_code.endswith(service.line_name):
                    vehicle_code = vehicle_code[:-len(service.line_name)]
                    journey.service = service
                    operator = 'MDCL'
                    break
        journey.vehicle, vehicle_created = Vehicle.objects.get_or_create({
            'source': self.source
        }, operator_id=operator, code=vehicle_code)

        return journey, vehicle_created

    def create_vehicle_location(self, item):
        return VehicleLocation(
            latlong=Point(item.vehicle.position.longitude, item.vehicle.position.latitude),
            datetime=timezone.make_aware(datetime.fromtimestamp(item.vehicle.timestamp)),
        )

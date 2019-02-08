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
            try:
                trip = Trip.objects.get(route__feed__name='tfwm', trip_id=journey.code)
            except Trip.DoesNotExist:
                print(item)
                pass
            if trip:
                journey.destination = trip.headsign
                operator = Operator.objects.get(name=trip.route.agency.name)

                try:
                    journey.service = Service.objects.get(operator=operator, line_name=trip.route.short_name, current=True)
                except Service.MultipleObjectsReturned as e:
                    print(e, operator, trip)

                if vehicle_code.endswith(trip.route.short_name):
                    vehicle_code = vehicle_code[:-len(trip.route.short_name)]

            journey.datetime = timezone.make_aware(
                datetime.strptime(item.vehicle.trip.start_date + item.vehicle.trip.start_time, '%Y%m%d%H:%M:%S')
            )

        # else:
        #     print(item)

        journey.vehicle, vehicle_created = Vehicle.objects.get_or_create({
            'source': self.source
        }, operator=operator, code=vehicle_code)

        return journey, vehicle_created

    def create_vehicle_location(self, item):
        return VehicleLocation(
            latlong=Point(item.vehicle.position.longitude, item.vehicle.position.latitude),
            datetime=timezone.make_aware(datetime.fromtimestamp(item.vehicle.timestamp)),
        )

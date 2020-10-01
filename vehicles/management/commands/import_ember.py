from ciso8601 import parse_datetime
from django.contrib.gis.geos import Point
from django.utils.timezone import localtime
from busstops.models import Service
from bustimes.models import Trip
from ...models import VehicleLocation, VehicleJourney
from ..import_live_vehicles import ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    url = 'https://api.ember.to/v1/vehicles/'
    source_name = 'Ember'

    @staticmethod
    def get_datetime(item):
        return parse_datetime(item['gps']['last_updated'])

    def get_vehicle(self, item):
        return self.vehicles.get_or_create(
            {
                'reg': item['plate_number'],
                'fleet_number': item['id']
            },
            operator_id='EMBR', code=item['plate_number']
        )

    def get_journey(self, item, vehicle):
        journey = VehicleJourney()
        journey.data = item

        trip = item['previous_trip']
        last_stop = trip['route'][-1]['departure']
        if 'actual' in last_stop:
            end = last_stop['actual']
        else:
            end = last_stop['scheduled']

        if parse_datetime(end) < self.source.datetime:
            trip = item['next_trip']

        journey.route_name = trip['route_number']
        journey.datetime = parse_datetime(trip['route'][0]['departure']['scheduled'])
        journey.service = Service.objects.get(current=True, operator='EMBR', line_name=journey.route_name)
        journey.destination = trip['route'][-1]['location']['region_name']

        time = localtime(journey.datetime).time()
        try:
            journey.trip = Trip.objects.get(route__service=journey.service, start=time)
        except (Trip.DoesNotExist, Trip.MultipleObjectsReturned) as e:
            print(e)

        return journey

    def create_vehicle_location(self, item):
        return VehicleLocation(
            latlong=Point(item['gps']['longitude'], item['gps']['latitude']),
        )

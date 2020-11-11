import ciso8601
from time import sleep
from datetime import timedelta
from pytz.exceptions import AmbiguousTimeError
from django.contrib.gis.geos import Point
from django.utils import timezone
from busstops.models import Service
from ...models import VehicleLocation, VehicleJourney
from ..import_live_vehicles import ImportLiveVehiclesCommand


def parse_datetime(string):
    try:
        return timezone.make_aware(ciso8601.parse_datetime(string))
    except AmbiguousTimeError:
        return timezone.make_aware(ciso8601.parse_datetime(string), is_dst=True)


class Command(ImportLiveVehiclesCommand):
    source_name = 'Megabus'
    operators = ['MEGA', 'SCMG']
    dead_trips = set()
    last_got_services = None
    last_got_trips = None

    @staticmethod
    def get_datetime(item):
        return parse_datetime(item['live']['timestamp']['dateTime'])

    def get_services(self):
        now = self.source.datetime
        if self.last_got_services:
            for service in self.services:
                yield service
            return
        self.services = []
        for string in ['m1', 'm2', 'm3', 'm4', 'm9']:
            url = f'{self.url}/getLookup.php/{string}?byservice=true'
            response = self.session.get(url, timeout=1)
            sleep(1)
            for service in response.json():
                yield service
                self.services.append(service)
        self.last_got_services = now

    def get_trips(self):
        now = self.source.datetime
        if self.last_got_trips and now - self.last_got_trips < timedelta(hours=3):
            for trip in self.trips:
                yield trip
            return
        self.trips = []
        for service in self.get_services():
            ticket_name = service['ticketName']
            response = self.session.get(f'{self.url}/getServices.php/{ticket_name}/0/service/', timeout=5)
            sleep(1)
            for trip in response.json()['services']:
                yield trip
                self.trips.append(trip)
        self.last_got_trips = now

    def get_items(self):
        now = self.source.datetime
        trips = self.get_trips()
        for trip in trips:
            start = parse_datetime(trip['startTime']['dateTime'])
            if start > now:
                continue
            end = parse_datetime(trip['endTime']['dateTime'])
            if end < now:
                continue
            link_date = trip['linkDate']
            route = trip['route']
            direction = trip['dir']
            journey = trip['journeyId']
            url = f'{link_date}/{route}/{direction}/{journey}'
            if url in self.dead_trips:
                continue
            try:
                response = self.session.get(f'{self.url}/getTrip.php/{url}/false', timeout=5)
            except Exception as e:
                print(e)
                sleep(1)
                continue
            sleep(1)
            if not response.ok:
                print(response.content)
                continue
            any_live = False
            for service in response.json()['services']:
                if service['live']:
                    any_live = True
                    yield service
            if not any_live:
                self.dead_trips.add(url)

    def get_vehicle(self, item):
        defaults = {
            'source': self.source
        }
        vehicle = item['live']['vehicle']
        if vehicle.isupper() and len(vehicle) == 8:
            defaults['reg'] = vehicle.replace(' ', '')
        return self.vehicles.get_or_create(defaults, operator_id=self.operators[0], code=vehicle)

    def get_journey(self, item, vehicle):
        journey = VehicleJourney()

        journey.datetime = parse_datetime(item['startTime']['dateTime'])

        latest_location = vehicle.latest_location
        if latest_location and journey.datetime == latest_location.journey.datetime:
            journey = latest_location.journey
        else:
            try:
                journey = VehicleJourney.objects.get(vehicle=vehicle, datetime=journey.datetime)
            except VehicleJourney.DoesNotExist:
                pass

        journey.route_name = item['route']
        journey.destination = item['arrival']

        latest_location = vehicle.latest_location
        if latest_location and journey.route_name == latest_location.journey.route_name:
            if latest_location.journey.service:
                journey.service = vehicle.latest_location.journey.service
                return journey

        route_name = journey.route_name
        if route_name[-1] == 'X':
            route_name = route_name[:-1]

        try:
            journey.service = Service.objects.get(operator__in=self.operators,
                                                  line_name=route_name,
                                                  current=True)
        except (Service.DoesNotExist, Service.MultipleObjectsReturned) as e:
            print(journey.route_name, e)

        return journey

    def create_vehicle_location(self, item):
        heading = item['live']['bearing']
        return VehicleLocation(
            latlong=Point(item['live']['lon'], item['live']['lat']),
            heading=heading
        )

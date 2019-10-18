from time import sleep
from datetime import timedelta
from ciso8601 import parse_datetime
from requests import RequestException
from django.contrib.gis.geos import Point
from django.utils import timezone
from busstops.models import Service
from bustimes.models import get_calendars, Trip
from ...models import VehicleLocation, VehicleJourney
from ..import_live_vehicles import ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    source_name = 'National coach code'
    operators = ['NATX', 'NXSH', 'NXAP', 'WAIR']
    url = ''

    @staticmethod
    def get_datetime(item):
        return timezone.make_aware(parse_datetime(item['live']['timestamp']['dateTime']))

    def get_items(self):
        url = 'https://coachtracker.nationalexpress.com/api/eta/routes/{}/{}'
        now = self.source.datetime
        time_since_midnight = timedelta(hours=now.hour, minutes=now.minute, seconds=now.second,
                                        microseconds=now.microsecond)
        trips = Trip.objects.filter(calendar__in=get_calendars(now),
                                    start__lte=time_since_midnight + timedelta(minutes=5),
                                    end__gte=time_since_midnight - timedelta(minutes=30))
        services = Service.objects.filter(operator__in=self.operators, route__trip__in=trips).distinct()
        for service in services.values('line_name'):
            for direction in 'OI':
                try:
                    res = self.session.get(url.format(service['line_name'], direction), timeout=5)
                except RequestException as e:
                    print(e)
                    continue
                if not res.ok:
                    print(res)
                    continue
                if direction != res.json()['dir']:
                    print(res.url)
                for item in res.json()['services']:
                    if item['live']:
                        yield(item)
            sleep(1.5)

    def get_vehicle(self, item):
        return self.vehicles.get_or_create(source=self.source, operator_id=self.operators[0],
                                           code=item['live']['vehicle'])

    def get_journey(self, item, vehicle):
        journey = VehicleJourney()
        journey.route_name = item['route']
        journey.destination = item['arrival']
        journey.code = item['journeyId']
        journey.datetime = timezone.make_aware(parse_datetime(item['startTime']['dateTime']))

        latest_location = vehicle.latest_location
        if latest_location and journey.route_name == latest_location.journey.route_name:
            journey.service = vehicle.latest_location.journey.service
        else:
            try:
                journey.service = Service.objects.get(operator__in=self.operators, line_name=journey.route_name,
                                                      current=True)
            except (Service.DoesNotExist, Service.MultipleObjectsReturned) as e:
                print(e)

        return journey

    def create_vehicle_location(self, item):
        heading = item['live']['bearing']
        if heading == -1:
            heading = None
        return VehicleLocation(
            latlong=Point(item['live']['lon'], item['live']['lat']),
            heading=heading
        )

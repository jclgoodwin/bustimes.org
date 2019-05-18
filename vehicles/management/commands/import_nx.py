from time import sleep
from ciso8601 import parse_datetime
from django.contrib.gis.geos import Point
from django.utils import timezone
from busstops.models import Service
from ...models import VehicleLocation, VehicleJourney
from ..import_live_vehicles import ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    source_name = 'National coach code'
    operators = ['NATX', 'NXSH', 'NXAP']
    url = ''

    @staticmethod
    def get_datetime(item):
        return timezone.make_aware(parse_datetime(item['live']['timestamp']['dateTime']))

    def get_items(self):
        url = 'https://coachtracker.nationalexpress.com/api/eta/routes/{}/{}'
        now = timezone.now()
        services = Service.objects.filter(journey__datetime__lte=now, journey__stopusageusage__datetime__gte=now,
                                          operator__in=self.operators).distinct().values('line_name')
        for service in services:
            for direction in 'OI':
                res = self.session.get(url.format(service['line_name'], direction))
                if direction != res.json()['dir']:
                    print(res.url)
                for item in res.json()['services']:
                    if item['live']:
                        yield(item)
            sleep(1.5)

    def get_vehicle(self, item):
        return self.vehicles.get_or_create(source=self.source, operator_id='NATX', code=item['live']['vehicle'])

    def get_journey(self, item, vehicle):
        journey = VehicleJourney()
        journey.route_name = item['route']
        journey.destination = item['arrival']
        journey.code = item['journeyId']
        journey.datetime = item['arrival']

        latest_location = vehicle.latest_location
        if latest_location and latest_location.current and journey.route_name == latest_location.journey.route_name:
            journey.service = vehicle.latest_location.journey.service
        else:
            try:
                journey.service = Service.objects.get(operator__in=self.operators, line_name=journey.route_name,
                                                      current=True)
            except (Service.DoesNotExist, Service.MultipleObjectsReturned) as e:
                print(e)

        return journey

    def create_vehicle_location(self, item):
        return VehicleLocation(
            latlong=Point(item['live']['lon'], item['live']['lat']),
            heading=item['live']['bearing']
        )

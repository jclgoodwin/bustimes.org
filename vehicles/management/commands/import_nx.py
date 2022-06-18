import ciso8601
from time import sleep
from datetime import timedelta
from requests import RequestException
from django.contrib.gis.geos import Point
from django.utils import timezone
from django.db.models import Exists, OuterRef, Q
from busstops.models import Service
from bustimes.utils import get_calendars
from bustimes.models import Trip
from ...models import Vehicle, VehicleLocation, VehicleJourney
from ..import_live_vehicles import ImportLiveVehiclesCommand


def parse_datetime(string):
    datetime = ciso8601.parse_datetime(string)
    return timezone.make_aware(datetime)


def get_trip_condition(date, time_since_midnight):
    return Q(
        calendar__in=get_calendars(date),
        start__lte=time_since_midnight + timedelta(minutes=5),
        end__gte=time_since_midnight - timedelta(minutes=30)
    )


class Command(ImportLiveVehiclesCommand):
    source_name = 'National coach code'
    operators = ['NATX', 'NXSH', 'NXAP', 'WAIR']
    url = 'https://coachtracker.nationalexpress.com/api/eta/routes/{}/{}'
    sleep = 1.5

    @staticmethod
    def get_datetime(item):
        return parse_datetime(item['live']['timestamp']['dateTime'])

    def get_items(self):
        now = self.source.datetime
        time_since_midnight = timedelta(hours=now.hour, minutes=now.minute, seconds=now.second)

        yesterday = now - timedelta(hours=24)
        time_since_yesterday_midnight = time_since_midnight + timedelta(hours=24)

        trips = Trip.objects.filter(
            get_trip_condition(now, time_since_midnight)
            | get_trip_condition(yesterday, time_since_yesterday_midnight)
        )
        has_trips = Exists(trips.filter(route__service=OuterRef('id')))

        services = Service.objects.filter(has_trips, operator__in=self.operators)
        for service in services.values('line_name'):
            line_name = service['line_name'].upper()
            for direction in 'OI':
                try:
                    res = self.session.get(self.url.format(line_name, direction), timeout=5)
                except RequestException as e:
                    print(e)
                    continue
                if not res.ok:
                    print(res.url, res)
                    continue
                if direction != res.json()['dir']:
                    print(res.url)
                for item in res.json()['services']:
                    if item['live']:
                        yield(item)
            self.save()
            sleep(self.sleep)

    def get_vehicle(self, item):
        code = item['live']['vehicle']
        if ' - ' in code:
            parts = code.split(' - ')
            if len(parts) == 2 and len(parts[1]) > 7:
                try:
                    return self.vehicles.get(code=parts[1]), False
                except (Vehicle.DoesNotExist, Vehicle.MultipleObjectsReturned):
                    pass
        else:
            try:
                return self.vehicles.get(code__endswith=f' - {code}'), False
            except (Vehicle.DoesNotExist, Vehicle.MultipleObjectsReturned):
                pass
        return self.vehicles.get_or_create(
            {'source': self.source},
            operator_id=self.operators[0],
            code=item['live']['vehicle']
        )

    def get_journey(self, item, vehicle):
        journey = VehicleJourney(
            datetime=parse_datetime(item['startTime']['dateTime']),
            route_name=item['route']
        )

        latest_journey = vehicle.latest_journey
        if latest_journey and journey.datetime == latest_journey.datetime:
            if journey.route_name == latest_journey.route_name and latest_journey.service_id:
                return latest_journey
            journey = latest_journey
        else:
            try:
                journey = VehicleJourney.objects.get(vehicle=vehicle, datetime=journey.datetime)
            except VehicleJourney.DoesNotExist:
                pass

        journey.destination = item['arrival']
        journey.direction = "outbound" if item["dir"] == "O" else "inbound"
        journey.code = item['journeyId']

        try:
            journey.service = Service.objects.get(operator__in=self.operators, line_name__iexact=journey.route_name,
                                                  current=True)
        except (Service.DoesNotExist, Service.MultipleObjectsReturned) as e:
            print(journey.route_name, e)

        if journey.service:
            journey.trip = journey.get_trip(departure_time=journey.datetime)

        return journey

    def create_vehicle_location(self, item):
        heading = item['live']['bearing']

        early = None
        for timetable in item['timetables']:
            if timetable and timetable['eta'] and timetable['eta']['status'] == 'next_stop':
                aimed_arrival = parse_datetime(timetable['arrive']['dateTime'])
                expected_arrival = parse_datetime(timetable['eta']['etaArrive']['dateTime'])
                early = (aimed_arrival - expected_arrival)
                break

        return VehicleLocation(
            latlong=Point(item['live']['lon'], item['live']['lat']),
            heading=heading,
            early=early
        )

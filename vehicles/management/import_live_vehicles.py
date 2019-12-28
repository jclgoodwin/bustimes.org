import math
import requests
import logging
import sys
from datetime import timedelta
from setproctitle import setproctitle
from time import sleep
from django.db import Error, IntegrityError, InterfaceError, transaction
from django.core.management.base import BaseCommand
from django.utils import timezone
from busstops.models import DataSource, ServiceCode
from ..models import Vehicle, VehicleLocation


logger = logging.getLogger(__name__)


def calculate_bearing(a, b):
    if a.equals_exact(b, 0.001):
        return

    a_lat = math.radians(a.y)
    a_lon = math.radians(a.x)
    b_lat = math.radians(b.y)
    b_lon = math.radians(b.x)

    y = math.sin(b_lon - a_lon) * math.cos(b_lat)
    x = math.cos(a_lat) * math.sin(b_lat) - math.sin(a_lat) * math.cos(b_lat) * math.cos(b_lon - b_lon)

    bearing_radians = math.atan2(y, x)
    bearing_degrees = math.degrees(bearing_radians)

    if bearing_degrees < 0:
        bearing_degrees += 360

    return bearing_degrees


def calculate_speed(a, b):
    time = b.datetime - a.datetime
    if time:
        distance = a.latlong.distance(b.latlong) * 69  # approximate miles
        return distance / time.total_seconds() * 60 * 60
    return 0


def same_journey(latest_location, journey, when):
    if not latest_location:
        return False
    if latest_location.journey.route_name and journey.route_name:
        same_route = latest_location.journey.route_name == journey.route_name
    else:
        same_route = latest_location.journey.service_id == journey.service_id
    if same_route:
        if latest_location.journey.code and journey.code:
            return str(latest_location.journey.code) == str(journey.code)
        if latest_location.journey.direction and journey.direction:
            return latest_location.journey.direction == journey.direction
        if latest_location.journey.trip:
            return latest_location.journey.trip.end > timedelta(hours=when.hour, minutes=when.minute,
                                                                seconds=when.second)
        return when - latest_location.datetime < timedelta(minutes=15)
    return False


class ImportLiveVehiclesCommand(BaseCommand):
    session = requests.Session()
    current_location_ids = set()
    vehicles = Vehicle.objects.select_related('latest_location__journey__service')

    @staticmethod
    def get_datetime(self):
        return

    def get_items(self):
        response = self.session.get(self.url, timeout=40)
        if response.ok:
            return response.json()

    def get_old_locations(self):
        return VehicleLocation.objects.filter(
            current=True, journey__source=self.source, latest_vehicle__isnull=False
        ).exclude(id__in=self.current_location_ids)

    @staticmethod
    def get_service(queryset, latlong):
        for filtered_queryset in (
            queryset,
            queryset.filter(geometry__bboverlaps=latlong.buffer(0.1)),
            queryset.filter(geometry__bboverlaps=latlong.buffer(0.05)),
            queryset.filter(geometry__bboverlaps=latlong)
        ):
            try:
                return filtered_queryset.get()
            except queryset.model.MultipleObjectsReturned:
                continue

    def handle_item(self, item, now, service_code=None):
        datetime = self.get_datetime(item)
        location = None
        vehicle, vehicle_created = self.get_vehicle(item)
        if not vehicle:
            return
        if vehicle_created:
            latest = None
        else:
            latest = vehicle.latest_location
            if latest:
                if datetime:
                    if latest.datetime >= datetime:
                        self.current_location_ids.add(latest.id)
                        return
                else:
                    location = self.create_vehicle_location(item)
                    if location.latlong.equals_exact(latest.latlong, 0.001):
                        self.current_location_ids.add(latest.id)
                        return
        journey = self.get_journey(item, vehicle)
        journey.vehicle = vehicle
        if not journey:
            return
        if latest and latest.current and latest.journey.source_id != self.source.id:
            if ((datetime or now) - latest.datetime).total_seconds() < 300:  # less than 5 minutes old
                if latest.journey.service_id or not journey.service:
                    return  # defer to other source
        if not location:
            location = self.create_vehicle_location(item)
        location.datetime = datetime
        if latest:
            if location.datetime:
                if location.datetime == latest.datetime:
                    self.current_location_ids.add(latest.id)
                    return
            elif location.latlong == latest.latlong and location.heading == latest.heading:
                self.current_location_ids.add(latest.id)
                return
        if not location.datetime:
            location.datetime = now
        if same_journey(latest, journey, location.datetime):
            changed = False
            if latest.journey.source_id != self.source.id:
                latest.journey.source = self.source
                changed = True
            if journey.service and not latest.journey.service:
                latest.journey.service = journey.service
                changed = True
            if journey.destination and not latest.journey.destination:
                latest.journey.destination = journey.destination
                changed = True
            if changed:
                latest.journey.save()
            location.journey = latest.journey
            if location.heading is None:
                location.heading = calculate_bearing(latest.latlong, location.latlong)
        else:
            journey.source = self.source
            if not journey.datetime:
                journey.datetime = location.datetime
            journey.save()
            if journey.service and not journey.service.tracking:
                journey.service.tracking = True
                journey.service.save(update_fields=['tracking'])
            if journey.service_id:
                if service_code and journey.service_id != service_code.service_id or self.source.name.endswith(' SIRI'):
                    if not journey.service.servicecode_set.filter(scheme__endswith=' SIRI').exists():
                        if service_code:
                            # doppelgänger
                            ServiceCode.objects.create(scheme=service_code.scheme, service=journey.service,
                                                       code=service_code.code)
                        else:
                            ServiceCode.objects.create(scheme=self.source.name, service=journey.service,
                                                       code=journey.route_name)
            location.journey = journey
        with transaction.atomic():
            # save new location
            location.current = True
            location.save()
            journey.vehicle.latest_location = location
            journey.vehicle.save(update_fields=['latest_location'])
            if latest:
                # mark old location as not current
                latest.current = False
                latest.save(update_fields=['current'])
        self.current_location_ids.add(location.id)
        vehicle.update_last_modified()

        if latest:
            speed = calculate_speed(latest, location)
            if speed > 90:
                print('{} mph\t{}'.format(speed, journey.vehicle.get_absolute_url()))
            elif speed < 1.5:
                last_three = list(location.journey.vehiclelocation_set.order_by('-id')[:3])
                if len(last_three) == 3:
                    speed = calculate_speed(last_three[2], last_three[0])
                    if speed < 1.5:
                        last_three[1].delete()

    def update(self):
        now = timezone.localtime()
        self.source, source_created = DataSource.objects.update_or_create(
            {'url': self.url, 'datetime': now},
            name=self.source_name
        )

        self.current_location_ids = set()

        try:
            items = self.get_items()
            if items:
                for item in items:
                    self.handle_item(item, now)
                # mark any vehicles that have gone offline as not current
                print(self.get_old_locations().update(current=False), end='\t', flush=True)
            else:
                return 300  # no items - wait five minutes
        except (requests.exceptions.RequestException, IntegrityError, TypeError, ValueError) as e:
            print(e)
            logger.error(e, exc_info=True)
            return 80

        time_taken = (timezone.now() - now).total_seconds()
        print(time_taken)
        if time_taken < 60:
            return 60 - time_taken
        return 0

    def handle(self, *args, **options):
        setproctitle(sys.argv[1].replace('import_', '', 1).replace('live_', '', 1))
        while True:
            try:
                wait = self.update()
            except Error as e:
                logger.error(e, exc_info=True)
                if type(e) is InterfaceError:
                    sys.exit()
                wait = 30
            sleep(wait)

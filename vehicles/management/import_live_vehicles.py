import math
import requests
import logging
import pid
from datetime import timedelta
from time import sleep
from django.core.management.base import BaseCommand
from django.db import IntegrityError
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

    return int(round(bearing_degrees))


def calculate_speed(a, b):
    time = b.datetime - a.datetime
    if time:
        distance = a.latlong.distance(b.latlong) * 69  # approximate miles
        return distance / time.total_seconds() * 60 * 60
    return 0


def same_journey(latest_location, journey, when):
    if not latest_location:
        return False
    if journey.id:
        return journey.id == latest_location.journey_id
    time_since_last_location = when - latest_location.datetime
    if time_since_last_location > timedelta(hours=1):
        return False
    if latest_location.journey.route_name and journey.route_name:
        same_route = latest_location.journey.route_name == journey.route_name
    else:
        same_route = latest_location.journey.service_id == journey.service_id
    if same_route:
        if latest_location.journey.datetime == journey.datetime:
            return True
        elif latest_location.journey.code and journey.code:
            return str(latest_location.journey.code) == str(journey.code)
        elif latest_location.journey.direction and journey.direction:
            if latest_location.journey.direction != journey.direction:
                return False
        return time_since_last_location < timedelta(minutes=15)
    return False


class ImportLiveVehiclesCommand(BaseCommand):
    session = requests.Session()
    current_location_ids = set()
    vehicles = Vehicle.objects.select_related('latest_location__journey__service')
    url = ''

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
        try:
            vehicle, vehicle_created = self.get_vehicle(item)
        except Vehicle.MultipleObjectsReturned as e:
            logger.error(e, exc_info=True)
            return
        if not vehicle:
            return

        if vehicle.withdrawn:
            vehicle.withdrawn = False
            vehicle.save(update_fields=['withdrawn'])

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
            try:
                journey.save()
            except IntegrityError as e:
                logger.error(e, exc_info=True)
                return
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
        if latest:
            location.id = latest.id
        location.current = True
        location.save()
        if not latest:
            journey.vehicle.latest_location = location
            journey.vehicle.save(update_fields=['latest_location'])
        self.current_location_ids.add(location.id)

        location.redis_append()
        location.channel_send(vehicle)

        if latest:
            speed = calculate_speed(latest, location)
            if speed > 90:
                print('{} mph\t{}'.format(speed, journey.vehicle.get_absolute_url()))

    def do_source(self):
        if self.url:
            self.source, _ = DataSource.objects.get_or_create(
                {'name': self.source_name},
                url=self.url
            )
        else:
            self.source, _ = DataSource.objects.get_or_create(name=self.source_name)
            self.url = self.source.url

    def update(self):
        now = timezone.localtime()
        self.source.datetime = now

        self.current_location_ids = set()

        items = self.get_items()
        if items:
            for item in items:
                self.handle_item(item, now)
            # mark any vehicles that have gone offline as not current
            self.get_old_locations().update(current=False)
        else:
            return 300  # no items - wait five minutes

        time_taken = (timezone.now() - now).total_seconds()
        if time_taken < 60:
            return 60 - time_taken
        return 0

    def handle(self, *args, **options):
        try:
            with pid.PidFile(self.source_name):
                self.do_source()
                while True:
                    wait = self.update()
                    self.source.save(update_fields=['datetime'])
                    sleep(wait)
                    if self.source_name == self.source.name:
                        previous_datetime = self.source.datetime
                        self.source.refresh_from_db()
                        assert self.source.datetime == previous_datetime
        except pid.PidFileError:
            return

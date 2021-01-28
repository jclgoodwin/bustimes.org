import math
import requests
import logging
import pid
import redis
from aioredis import ReplyError
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from channels.exceptions import ChannelFull
from datetime import timedelta
from time import sleep
from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings
from django.db import connections, IntegrityError
from django.db.models import Exists, OuterRef, Q
from django.db.models.functions import Now
from django.utils import timezone
from bustimes.models import Route
from busstops.models import DataSource
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
    latest_journey = latest_location.journey
    if journey.id:
        return journey.id == latest_journey.id
    time_since_last_location = when - latest_location.datetime
    if time_since_last_location > timedelta(hours=1):
        return False
    if latest_journey.route_name and journey.route_name:
        same_route = latest_journey.route_name == journey.route_name
    else:
        same_route = latest_journey.service_id == journey.service_id
    if same_route:
        if latest_journey.datetime == journey.datetime:
            return True
        elif latest_journey.code and journey.code:
            return str(latest_journey.code) == str(journey.code)
        elif latest_journey.direction and journey.direction:
            if latest_journey.direction != journey.direction:
                return False
        elif latest_journey.destination and journey.destination:
            return latest_journey.destination == journey.destination
        return time_since_last_location < timedelta(minutes=15)
    return False


class ImportLiveVehiclesCommand(BaseCommand):
    url = ''
    vehicles = Vehicle.objects.select_related('latest_location__journey__service', 'livery')
    wait = 60

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = requests.Session()
        self.current_location_ids = set()
        self.to_save = []

    @staticmethod
    def get_datetime(self):
        return

    def get_items(self):
        response = self.session.get(self.url, timeout=40)
        if response.ok:
            return response.json()

    @staticmethod
    def get_service(queryset, latlong):
        for filtered_queryset in (
            queryset,
            queryset.filter(
                Exists(
                    Route.objects.filter(
                        Q(end_date__gte=Now()) | Q(end_date=None),
                        Q(start_date__lte=Now()) | Q(start_date=None),
                        service=OuterRef('id')
                    )
                )
            ),
            queryset.filter(geometry__bboverlaps=latlong.buffer(0.1)),
            queryset.filter(geometry__bboverlaps=latlong.buffer(0.05)),
            queryset.filter(geometry__bboverlaps=latlong)
        ):
            try:
                return filtered_queryset.get()
            except queryset.model.MultipleObjectsReturned:
                continue

    def handle_item(self, item, now=None):
        datetime = self.get_datetime(item)
        location = None
        try:
            vehicle, vehicle_created = self.get_vehicle(item)
        except Vehicle.MultipleObjectsReturned as e:
            logger.error(e, exc_info=True)
            return
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

                # take a snapshot here, to see if they have changed later,
                # cos get_journey() might return latest.journey
                original_service = latest.journey.service
                original_destination = latest.journey.destination

        try:
            journey = self.get_journey(item, vehicle)
        except ObjectDoesNotExist:
            vehicle.latest_location_id = None
            vehicle.save(update_fields=['latest_location'])
            latest = None
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
            if not location.latlong or not (location.latlong.x or location.latlong.y):  # (0, 0) - null island
                return

        if location.heading == -1:
            location.heading = None
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
            if journey.service and not original_service:
                latest.journey.service = journey.service
                changed = True
            if journey.destination and not original_destination:
                latest.journey.destination = journey.destination
                changed = True
            if changed:
                latest.journey.save()
            location.journey = latest.journey
            if location.heading is None:
                location.heading = calculate_bearing(latest.latlong, location.latlong)
                if location.heading is None:
                    location.heading = latest.heading
        else:
            journey.source = self.source
            if not journey.datetime:
                journey.datetime = location.datetime
            try:
                journey.save()
            except IntegrityError:
                journey = vehicle.vehiclejourney_set.using('default').get(datetime=journey.datetime)

            if journey.service and not journey.service.tracking:
                journey.service.tracking = True
                journey.service.save(update_fields=['tracking'])

            location.journey = journey
        if latest:
            location.id = latest.id
        location.current = True

        self.to_save.append((location, latest, vehicle))

    def save(self):
        if not self.to_save:
            return

        to_create = []
        to_update = []
        for location, latest, vehicle in self.to_save:
            if location.id:
                to_update.append(location)
            else:
                to_create.append(location)

        VehicleLocation.objects.bulk_create(to_create)
        if to_update:
            VehicleLocation.objects.bulk_update(to_update, fields=['datetime', 'latlong', 'journey', 'occupancy',
                                                                   'heading', 'early', 'delay', 'current'])

        group_messages = {}
        channel_messages = {}

        r = redis.from_url(settings.REDIS_URL)
        pipeline = r.pipeline(transaction=False)

        query = ", ".join("bounds && %s" for location in self.to_save)
        query = f"SELECT name, {query} FROM vehicles_channel"

        with connections[settings.READ_DATABASE].cursor() as cursor:
            cursor.execute(query, [location.latlong.wkt for location, _, _ in self.to_save])
            channels = cursor.fetchall()

        i = 1
        for location, latest, vehicle in self.to_save:
            if not vehicle.latest_location_id:
                vehicle.latest_location = location
                vehicle.save(update_fields=['latest_location'])

            self.current_location_ids.add(location.id)

            pipeline.rpush(*location.get_appendage())

            message = location.get_message(vehicle)

            if location.journey.service_id:
                group = f'service{location.journey.service_id}'
                if group in group_messages:
                    group_messages[group].append(message)
                else:
                    group_messages[group] = [message]

            if vehicle.operator_id:
                group = f'operator{vehicle.operator_id}'
                if group in group_messages:
                    group_messages[group].append(message)
                else:
                    group_messages[group] = [message]

            for channel in channels:
                if channel[i]:
                    name = channel[0]
                    if name in channel_messages:
                        channel_messages[name].append(message)
                    else:
                        channel_messages[name] = [message]
            i += 1

            if vehicle.withdrawn:
                vehicle.withdrawn = False
                vehicle.save(update_fields=['withdrawn'])

            if latest:
                speed = calculate_speed(latest, location)
                if speed > 90:
                    print('{} mph\t{}'.format(speed, vehicle.get_absolute_url()))

        channel_layer = get_channel_layer()
        group_send = async_to_sync(channel_layer.group_send)
        send = async_to_sync(channel_layer.send)

        try:
            for group in group_messages:
                group_send(group, {
                    'type': 'move_vehicles',
                    'items': group_messages[group]
                })
            for channel_name in channel_messages:
                try:
                    send(channel_name, {
                        'type': 'move_vehicles',
                        'items': channel_messages[channel_name]
                    })
                except ChannelFull:
                    pass
        except ReplyError:
            pass

        try:
            pipeline.execute()
        except redis.exceptions.ConnectionError:
            pass

        self.to_save = []

    def do_source(self):
        if self.url:
            self.source, _ = DataSource.objects.get_or_create(
                {'name': self.source_name},
                url=self.url
            )
        else:
            self.source, _ = DataSource.objects.get_or_create(name=self.source_name)
            self.url = self.source.url
        return self

    def update(self):
        now = timezone.now()
        self.source.datetime = now

        self.current_location_ids = set()

        try:
            items = self.get_items()
            if items:
                i = 0
                for item in items:
                    try:
                        self.handle_item(item, now)
                    except IntegrityError as e:
                        logger.error(e, exc_info=True)
                    i += 1
                    if i == 50:
                        self.save()
                        i = 0
                self.save()
                # mark any vehicles that have gone offline as not current
                # self.get_old_locations().update(current=False)
            else:
                return 300  # no items - wait five minutes
        except requests.exceptions.RequestException as e:
            logger.error(e, exc_info=True)
            return 120

        time_taken = (timezone.now() - now).total_seconds()
        if time_taken < self.wait:
            return self.wait - time_taken
        return 0  # took longer than self.wait

    def handle(self, *args, **options):
        # sleep(self.wait)
        with pid.PidFile(self.source_name):
            self.do_source()
            while True:
                wait = self.update()
                sleep(wait)

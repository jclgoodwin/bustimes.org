import math
import beeline
import requests
import logging
import redis
import json
from ciso8601 import parse_datetime
from datetime import timedelta
from time import sleep
from django.core.management.base import BaseCommand
from django.core.serializers.json import DjangoJSONEncoder
from django.conf import settings
from django.contrib.gis.geos import Point
from django.db import IntegrityError
from django.db.models import Exists, OuterRef, Q
from django.db.models.functions import Now
from django.utils import timezone
from bustimes.models import Route
from busstops.models import DataSource
from ..models import Vehicle, VehicleJourney


logger = logging.getLogger(__name__)
fifteen_minutes = timedelta(minutes=15)
twelve_hours = timedelta(hours=12)


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


def same_journey(latest_journey, journey, latest_datetime, when):
    if not latest_journey:
        return False

    if journey.id:
        return journey.id == latest_journey.id

    if latest_journey.datetime == journey.datetime:
        return True

    if latest_journey.route_name and journey.route_name:
        same_route = latest_journey.route_name == journey.route_name
    else:
        same_route = latest_journey.service_id == journey.service_id

    if not same_route:
        return False

    if (when - latest_journey.datetime) > twelve_hours:
        return False

    if latest_journey.code and journey.code:
        return str(latest_journey.code) == str(journey.code)

    if latest_journey.direction and journey.direction:
        if latest_journey.direction != journey.direction:
            return False
    elif latest_journey.destination and journey.destination:
        return latest_journey.destination == journey.destination

    # last time was less than 15 minutes ago
    if latest_datetime and (when - latest_datetime) < fifteen_minutes:
        return True

    return False


class ImportLiveVehiclesCommand(BaseCommand):
    url = ''
    vehicles = Vehicle.objects.select_related('latest_location__journey', 'latest_journey')
    wait = 60

    @staticmethod
    def add_arguments(parser):
        parser.add_argument('--immediate', action='store_true')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = requests.Session()
        self.redis = redis.from_url(settings.REDIS_URL)
        self.to_save = []
        self.vehicles_to_update = []

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
        if now and datetime and now < datetime:
            datetime = None  # datetime was in the future (probably The Green Bus)

        location = None
        try:
            vehicle, vehicle_created = self.get_vehicle(item)
        except Vehicle.MultipleObjectsReturned as e:
            logger.error(e, exc_info=True)
            return
        if not vehicle:
            return

        latest = None
        latest_datetime = None

        latest = self.redis.get(f'vehicle{vehicle.id}')
        if latest:
            latest = json.loads(latest)
            latest_datetime = parse_datetime(latest['datetime'])
            latest_latlong = Point(*latest['coordinates'])

            if datetime:
                if latest_datetime >= datetime:
                    # timestamp isn't newer
                    return
            else:
                location = self.create_vehicle_location(item)
                if location.latlong.equals_exact(latest_latlong, 0.001):
                    # position hasn't changed
                    return
        elif now and datetime and (now - datetime).total_seconds() > 600:
            # more than 10 minutes old
            return

        latest_journey = vehicle.latest_journey
        if latest_journey:
            # take a snapshot here, to see if they have changed later,
            # cos get_journey() might return same object
            original_service_id = latest_journey.service_id
            original_destination = latest_journey.destination

        journey = self.get_journey(item, vehicle)
        if not journey:
            return
        journey.vehicle = vehicle

        if latest and latest_journey:
            if latest_journey.source_id != self.source.id and self.source.name != 'Bus Open Data':
                if ((datetime or now) - latest_datetime).total_seconds() < 300:  # less than 5 minutes old
                    if latest_journey.service_id or not journey.service_id:
                        return  # defer to other source

        if not latest and now and datetime:
            if (now - datetime).total_seconds() > 900:
                return  # more than 15 minutes old

        if not location:
            location = self.create_vehicle_location(item)

        if not location.latlong or not (location.latlong.x or location.latlong.y):  # (0, 0) - null island
            return

        if location.heading == -1:
            location.heading = None

        location.datetime = datetime
        if not location.datetime:
            location.datetime = now

        if same_journey(latest_journey, journey, latest_datetime, location.datetime):
            changed = []
            if latest_journey.source_id != self.source.id:
                latest_journey.source = self.source
                changed.append('source')
            if journey.service_id and not original_service_id:
                latest_journey.service_id = journey.service_id
                changed.append('service')
            if journey.destination and not original_destination:
                latest_journey.destination = journey.destination
                changed.append('destination')
            if changed:
                latest_journey.save(update_fields=changed)

            journey = latest_journey

            if latest and location.heading is None:
                location.heading = calculate_bearing(latest_latlong, location.latlong)
                if location.heading is None:
                    location.heading = latest['heading']
        else:
            journey.source = self.source
            if not journey.datetime:
                journey.datetime = location.datetime
            try:
                journey.save()
            except IntegrityError:
                journey = vehicle.vehiclejourney_set.defer('data').using('default').get(datetime=journey.datetime)

            if journey.service_id and VehicleJourney.service.is_cached(journey):
                if not journey.service.tracking:
                    journey.service.tracking = True
                    journey.service.save(update_fields=['tracking'])

        if not location.id:
            location.id = vehicle.latest_location_id
        location.journey = journey
        location.current = True

        to_update = False

        if not location.id:
            location.save()
            vehicle.latest_location = location
            to_update = True

        vehicle.withdrawn = False

        if vehicle.latest_journey_id != journey.id:
            vehicle.latest_journey = journey
            to_update = True

        if to_update:
            self.vehicles_to_update.append(vehicle)

        self.to_save.append((location, vehicle))

    def save(self):
        if not self.to_save:
            return

        if self.vehicles_to_update:
            Vehicle.objects.bulk_update(self.vehicles_to_update, ['latest_journey', 'latest_location', 'withdrawn'])
            self.vehicles_to_update = []

        pipeline = self.redis.pipeline(transaction=False)

        for location, vehicle in self.to_save:
            lon = location.latlong.x
            lat = location.latlong.y
            if -180 <= lon <= 180 and -85.05112878 <= lat <= 85.05112878:
                pipeline.geoadd('vehicle_location_locations', lon, lat, vehicle.id)
                redis_json = location.get_redis_json(vehicle)
                redis_json = json.dumps(redis_json, cls=DjangoJSONEncoder)
                pipeline.set(f'vehicle{vehicle.id}', redis_json, ex=900)

        with beeline.tracer(name="pipeline"):
            try:
                pipeline.execute()
            except redis.exceptions.ConnectionError:
                pass

        pipeline = self.redis.pipeline(transaction=False)

        for location, vehicle in self.to_save:
            pipeline.rpush(*location.get_appendage())

        self.to_save = []

        with beeline.tracer(name="pipeline"):
            try:
                pipeline.execute()
            except redis.exceptions.ConnectionError:
                pass

    def do_source(self):
        if self.url:
            self.source, _ = DataSource.objects.get_or_create(
                {'name': self.source_name},
                url=self.url
            )
        else:
            self.source = DataSource.objects.get(name=self.source_name)
            self.url = self.source.url
        return self

    def update(self):
        now = timezone.now()
        self.source.datetime = now

        try:
            items = self.get_items()
            if items:
                i = 0
                for item in items:
                    try:
                        # use `self.source.datetime` instead of `now`,
                        # so `get_items` can increment the time
                        # if it involves multiple spread out requests
                        self.handle_item(item, self.source.datetime)
                    except IntegrityError as e:
                        logger.error(e, exc_info=True)
                    i += 1
                    if i == 50:
                        self.save()
                        i = 0
                self.save()
            else:
                return 300  # no items - wait five minutes
        except requests.exceptions.RequestException as e:
            logger.error(e, exc_info=True)
            return 120

        time_taken = (timezone.now() - now).total_seconds()
        if time_taken < self.wait:
            return self.wait - time_taken
        return 0  # took longer than self.wait

    def handle(self, immediate=False, *args, **options):
        if not immediate:
            sleep(self.wait)
        self.do_source()
        while True:
            wait = self.update()
            sleep(wait)

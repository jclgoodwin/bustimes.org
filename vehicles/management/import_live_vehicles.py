import json
import logging
from collections import namedtuple
from datetime import timedelta
from time import sleep

import requests
import sentry_sdk
from ciso8601 import parse_datetime
from django.contrib.gis.geos import Point
from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.core.serializers.json import DjangoJSONEncoder
from django.db import IntegrityError
from django.db.models import Exists, OuterRef, Q, F
from django.db.models.functions import Now
from django.utils import timezone
from redis.exceptions import ConnectionError
from tenacity import before_sleep_log, retry, wait_exponential

from busstops.models import DataSource
from bustimes.models import Route, Trip

from ..models import Vehicle, VehicleJourney, VehicleCode
from ..utils import calculate_bearing, redis_client

logger = logging.getLogger(__name__)
fifteen_minutes = timedelta(minutes=15)
twelve_hours = timedelta(hours=12)


Status = namedtuple(
    "Status",
    ("fetched_at", "timestamp", "age", "total_items", "changed_items", "time_taken"),
)


def same_journey(latest_journey, journey, latest_datetime, when):
    if not latest_journey:
        return False

    if journey.id:
        return latest_journey.id == journey.id

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
        return (latest_journey.code, latest_journey.destination) == (
            journey.code,
            journey.destination,
        )

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
    url = ""
    vehicles = Vehicle.objects.select_related("latest_journey__trip")
    wait = 60
    history = True
    status = []
    status_key = None

    @staticmethod
    def add_arguments(parser):
        parser.add_argument("--immediate", action="store_true")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = requests.Session()
        self.to_save = []
        self.vehicles_to_update = []
        self.identifiers = {}
        self.journeys_ids = {}
        self.journeys_ids_ids = {}

    @staticmethod
    def get_datetime(self):
        return

    @retry(
        wait=wait_exponential(multiplier=1, min=4, max=10),
        before_sleep=before_sleep_log(logger, logging.ERROR),
    )
    def get_items(self):
        response = self.session.get(self.url, timeout=20)
        response.raise_for_status()
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
                        service=OuterRef("id"),
                    )
                )
            ),
            queryset.filter(geometry__bboverlaps=latlong.buffer(0.1)),
            queryset.filter(geometry__bboverlaps=latlong.buffer(0.05)),
            queryset.filter(geometry__bboverlaps=latlong),
        ):
            try:
                return filtered_queryset.get()
            except queryset.model.MultipleObjectsReturned:
                continue

    def handle_item(self, item, now=None, vehicle=None, latest=None, keep_journey=None):
        datetime = self.get_datetime(item)
        if now and datetime and now < datetime:
            difference = datetime - now
            if difference > twelve_hours:
                datetime = None  # datetime more than 12 hours in the future (probably The Green Bus)
            if 3000 < difference.total_seconds() <= 600:
                logger.warning("datetime %s is in the future", datetime)

        location = None
        if vehicle is None:
            try:
                vehicle, _ = self.get_vehicle(item)
            except Vehicle.MultipleObjectsReturned as e:
                logger.exception(e)
                return
            if not vehicle:
                return

        latest_datetime = None

        if latest is None:
            latest = redis_client.get(f"vehicle{vehicle.id}")
            if latest:
                latest = json.loads(latest)
        if latest:
            latest_datetime = parse_datetime(latest["datetime"])
            latest_latlong = Point(*latest["coordinates"])

            if datetime and latest_datetime >= datetime:
                # timestamp isn't newer
                return
            else:
                location = self.create_vehicle_location(item)
                if not location or location.latlong.equals_exact(latest_latlong):
                    if datetime:
                        # location hasn't changed
                        # - so assume the data is old
                        # – if the vehicle was really stationary the location would "drift" a bit
                        datetime = latest_datetime
                    else:
                        return
        # elif now and datetime and (now - datetime).total_seconds() > 600:
        #     # more than 10 minutes old
        #     return

        latest_journey = vehicle.latest_journey
        if latest_journey:
            # take a snapshot here, to see if they have changed later,
            # cos get_journey() might return same object
            original_service_id = latest_journey.service_id
            original_destination = latest_journey.destination

        if keep_journey:
            journey = latest_journey
        else:
            journey = self.get_journey(item, vehicle)

            if (
                journey
                and journey.trip
                and journey.trip.garage_id
                and journey.trip.garage_id != vehicle.garage_id
            ):
                vehicle.garage_id = journey.trip.garage_id
                vehicle.save(update_fields=["garage"])

        if not journey:
            return
        journey.vehicle = vehicle

        if (
            latest
            and latest_journey
            and latest_journey.source_id != self.source.id
            and self.source.name != "Bus Open Data"
        ):
            if ((datetime or now) - latest_datetime).total_seconds() < 300:
                # less than 5 minutes old
                if latest_journey.service_id or not journey.service_id:
                    return  # defer to other source

        # if not latest and now and datetime:
        #     if (now - datetime).total_seconds() > 900:
        #         return  # more than 15 minutes old

        if not location:
            location = self.create_vehicle_location(item)
            if not location:
                return

        if (
            not (location.latlong.x or location.latlong.y)  # (0, 0) - null island
            or (location.latlong.x == 1 and location.latlong.y == 1)
            or not (
                -180 <= location.latlong.x <= 180
                and -85.05112878 <= location.latlong.y <= 85.05112878
            )
        ):
            location.latlong = None

        if location.heading == -1:
            location.heading = None

        location.datetime = datetime
        if not location.datetime:
            location.datetime = now

        if latest and location.latlong and location.heading is None:
            if latest_latlong.equals_exact(location.latlong, 0.001):
                location.heading = latest["heading"]
            else:
                location.heading = calculate_bearing(latest_latlong, location.latlong)

        if keep_journey:
            pass
        elif same_journey(latest_journey, journey, latest_datetime, location.datetime):
            changed = []
            if latest_journey.source_id != self.source.id:
                latest_journey.source = self.source
                changed.append("source")
            if journey.service_id != original_service_id:
                latest_journey.service_id = journey.service_id
                changed.append("service")
            if journey.destination != original_destination:
                latest_journey.destination = journey.destination
                changed.append("destination")
            if journey.datetime and journey.datetime != latest_journey.datetime:
                latest_journey.datetime = journey.datetime
                changed.append("datetime")
            if changed:
                latest_journey.save(update_fields=changed)
                if changed != ["source"]:
                    cache.delete(f"journey{latest_journey.id}")

            journey = latest_journey

        else:
            journey.source = self.source
            if not journey.datetime:
                journey.datetime = location.datetime
            try:
                journey.save()
            except IntegrityError as e:
                try:
                    journey = vehicle.vehiclejourney_set.using("default").get(
                        datetime=journey.datetime
                    )
                except VehicleJourney.DoesNotExist:
                    logger.exception(e)

            if journey.service_id and VehicleJourney.service.is_cached(journey):
                if not journey.service.tracking:
                    journey.service.tracking = True
                    journey.service.save(update_fields=["tracking"])

        location.id = vehicle.id
        location.journey = journey

        if vehicle.latest_journey_id != journey.id:
            vehicle.latest_journey = journey
            if type(item) is dict:
                vehicle.latest_journey_data = item
            self.vehicles_to_update.append(vehicle)

        self.to_save.append((location, vehicle))

        return location, vehicle

    def save(self):
        if not self.to_save:
            return

        # update vehicle records if necessary

        if self.vehicles_to_update:
            try:
                Vehicle.objects.bulk_update(
                    self.vehicles_to_update,
                    ["latest_journey", "latest_journey_data"],
                )
            except IntegrityError as e:
                logger.exception(e)
            self.vehicles_to_update = []

        # update locations in Redis

        pipeline = redis_client.pipeline(transaction=False)

        geoadd = []
        sadd = {}

        for location, vehicle in self.to_save:
            if not location.latlong or (
                self.source.datetime
                and (self.source.datetime - location.datetime).total_seconds() > 600
            ):
                continue

            # update live map

            geoadd += [location.latlong.x, location.latlong.y, vehicle.id]

            if location.journey.service_id:
                key = f"service{location.journey.service_id}vehicles"
                if key in sadd:
                    sadd[key].append(vehicle.id)
                else:
                    sadd[key] = [vehicle.id]
            if vehicle.operator_id:
                key = f"operator{vehicle.operator_id}vehicles"
                if key in sadd:
                    sadd[key].append(vehicle.id)
                else:
                    sadd[key] = [vehicle.id]
            try:
                if (
                    location.journey.trip
                    and location.journey.trip.operator_id
                    and location.journey.trip.operator_id != vehicle.operator_id
                ):
                    key = f"operator{location.journey.trip.operator_id}vehicles"
                    if key in sadd:
                        sadd[key].append(vehicle.id)
                    else:
                        sadd[key] = [vehicle.id]
            except Trip.DoesNotExist:
                location.journey.trip = None

            redis_json = location.get_redis_json()
            redis_json = json.dumps(redis_json, cls=DjangoJSONEncoder)
            pipeline.set(f"vehicle{vehicle.id}", redis_json, ex=900)
            # can't use 'mset' cos it doesn't let us specify an expiry (900 secs = 15 min)

        if geoadd:
            pipeline.geoadd("vehicle_location_locations", geoadd)
        for key in sadd:
            pipeline.sadd(key, *sadd[key])

        if self.history:
            # add locations to journey history

            for location, vehicle in self.to_save:
                if location.latlong:
                    pipeline.rpush(*location.get_appendage())

        try:
            pipeline.execute()
        except ConnectionError as e:
            logger.exception(e)

        self.to_save = []

    def do_source(self):
        if self.url:
            self.source, _ = DataSource.objects.get_or_create(
                {"name": self.source_name}, url=self.url
            )
        else:
            self.source = DataSource.objects.get(name=self.source_name)
            self.url = self.source.url
        return self

    def handle_items(self, items, identities):
        with sentry_sdk.start_span(name="get vehicle codes"):
            vehicles = (
                Vehicle.objects.filter(
                    vehiclecode__code__in=identities,
                    vehiclecode__scheme=self.vehicle_code_scheme,
                )
                .annotate(code_code=F("vehiclecode__code"))
                .defer("latest_journey_data", "data")
            )
            vehicles_by_identity = {v.code_code: v for v in vehicles}

        vehicle_locations = redis_client.mget([f"vehicle{v.id}" for v in vehicles])
        vehicle_locations = {
            v.id: json.loads(item)
            for v, item in zip(vehicles, vehicle_locations)
            if item
        }

        for item, vehicle_identity in zip(items, identities):
            journey_identity = self.journeys_ids[vehicle_identity]

            if vehicle_identity in vehicles_by_identity:
                vehicle = vehicles_by_identity[vehicle_identity]
            else:
                vehicle, created = self.get_vehicle(item)
                # print(vehicle_identity, vehicle, created)
                if vehicle:
                    VehicleCode.objects.create(
                        code=vehicle_identity,
                        scheme=self.vehicle_code_scheme,
                        vehicle=vehicle,
                    )

            keep_journey = False
            if vehicle_identity in self.journeys_ids_ids:
                journey_identity_id = self.journeys_ids_ids[vehicle_identity]
                if journey_identity_id == (journey_identity, vehicle.latest_journey_id):
                    keep_journey = True  # can dumbly keep same latest_journey

            if vehicle:
                result = self.handle_item(
                    item,
                    self.source.datetime,
                    vehicle=vehicle,
                    latest=vehicle_locations.get(vehicle.id, False),
                    keep_journey=keep_journey,
                )

                if result:
                    location, vehicle = result

                    self.journeys_ids_ids[vehicle_identity] = (
                        journey_identity,
                        vehicle.latest_journey_id,
                    )

            self.identifiers[vehicle_identity] = self.get_item_identity(item)

        self.save()

    def get_changed_items(self, items=None):
        changed_items = []
        changed_journey_items = []
        changed_item_identities = []
        changed_journey_identities = []
        # (changed items and changed journey items are separate
        # so we can do the quick ones first)

        total_items = 0

        for i, item in enumerate(items or self.get_items() or ()):
            vehicle_identity = self.get_vehicle_identity(item)

            journey_identity = self.get_journey_identity(item)

            total_items += 1

            if self.identifiers.get(vehicle_identity) == self.get_item_identity(item):
                if journey_identity == self.journeys_ids[vehicle_identity]:
                    continue
                print(self.journeys_ids[vehicle_identity], item)
            if (
                vehicle_identity not in self.journeys_ids
                or journey_identity != self.journeys_ids[vehicle_identity]
            ):
                changed_journey_items.append(item)
                changed_journey_identities.append(vehicle_identity)
            else:
                changed_items.append(item)
                changed_item_identities.append(vehicle_identity)

            self.journeys_ids[vehicle_identity] = journey_identity

        return (
            changed_items,
            changed_journey_items,
            changed_item_identities,
            changed_journey_identities,
            total_items,
        )

    def update(self) -> int:
        with sentry_sdk.start_transaction(name=f"{self.source.name} update"):
            now = timezone.localtime()
            self.source.datetime = now

            wait = self.wait

            with sentry_sdk.start_span(name="get changed items"):
                try:
                    (
                        changed_items,
                        changed_journey_items,
                        changed_item_identities,
                        changed_journey_identities,
                        total_items,
                    ) = self.get_changed_items()
                except requests.exceptions.RequestException as e:
                    logger.exception(e)
                    return 120

            with sentry_sdk.start_span(name="handle quick items") as span:
                span.set_data("count", len(changed_items))
                self.handle_items(changed_items, changed_item_identities)
            with sentry_sdk.start_span(name="handle changed journey items") as span:
                span.set_data("count", len(changed_journey_items))
                self.handle_items(changed_journey_items, changed_journey_identities)

        if not total_items:
            return 120

        time_taken = (timezone.now() - now).total_seconds()

        if self.source_name:
            self.status.append(
                Status(
                    self.source.datetime,
                    None,
                    None,
                    total_items,
                    len(changed_items) + len(changed_journey_items),
                    time_taken,
                )
            )
            self.status = self.status[-50:]
            cache.set(self.status_key, self.status, None)

        if time_taken < wait:
            return wait - time_taken
        return 0  # took longer than minimum wait

    def handle(self, immediate=False, *args, **options):
        if self.source_name:
            self.status_key = f"{self.source_name.replace(' ', '_')}_status"
            try:
                self.status = cache.get(self.status_key, [])
            except TypeError:
                self.status = []

        if not immediate:
            sleep(self.wait)
        self.do_source()
        while True:
            wait = self.update()
            sleep(wait)

import math
import requests
import logging
import sys
from setproctitle import setproctitle
from time import sleep
from django.db import Error, IntegrityError, transaction
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


def same_journey(latest_location, journey):
    if not latest_location:
        return False
    if journey.code and latest_location.journey.code != str(journey.code):
        return False
    if latest_location.current:
        if latest_location.journey.route_name:
            return latest_location.journey.route_name == journey.route_name
        return latest_location.journey.service_id == journey.service_id
    if journey.code and latest_location.journey.code == str(journey.code):
        return True


class ImportLiveVehiclesCommand(BaseCommand):
    session = requests.Session()
    current_location_ids = set()
    vehicles = Vehicle.objects.select_related('latest_location__journey__service')

    @staticmethod
    def get_datetime(self):
        return

    def get_vehicle(self, item):
        raise NotImplementedError

    def get_items(self):
        response = self.session.get(self.url, timeout=40)
        if response.ok:
            return response.json()

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
            except queryset.model.DoesNotExist:
                break

        now = timezone.now()
        return queryset.filter(journey__datetime__lte=now,
                               journey__stopusageusage__datetime__gte=now).distinct().get()

    @transaction.atomic
    def handle_item(self, item, now, service_code=None):
        datetime = self.get_datetime(item)
        location = None
        try:
            vehicle, vehicle_created = self.get_vehicle(item)
            if not vehicle:
                return
            if not vehicle_created:
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
        except NotImplementedError:
            journey, vehicle_created = self.get_journey(item)
        if not journey:
            return
        if vehicle_created:
            latest = None
        else:
            latest = journey.vehicle.latest_location
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
        if same_journey(latest, journey):
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
                journey.service.save()
            if service_code and journey.service_id and journey.service_id != service_code.service_id:
                # doppelgänger
                if not journey.service.servicecode_set.filter(scheme__endswith=' SIRI').exists():
                    ServiceCode.objects.create(scheme=service_code.scheme, service=journey.service,
                                               code=service_code.code)
            location.journey = journey
        # save new location
        location.current = True
        location.save()
        journey.vehicle.latest_location = location
        journey.vehicle.save()
        self.current_location_ids.add(location.id)
        if latest:
            # mark old location as not current
            latest.current = False
            latest.save()

            distance = latest.latlong.distance(location.latlong) * 69
            time = location.datetime - latest.datetime
            if time:
                speed = distance / time.total_seconds() * 60 * 60
                if speed > 70:
                    print('{} mph\t{}'.format(speed, journey.vehicle.get_absolute_url()))

    def update(self):
        now = timezone.now()
        self.source, source_created = DataSource.objects.update_or_create(
            {'url': self.url, 'datetime': now},
            name=self.source_name
        )

        self.current_location_ids = set()

        current_locations = VehicleLocation.objects.filter(journey__source=self.source, current=True,
                                                           latest_vehicle__isnull=False)

        try:
            items = self.get_items()
            if items:
                for item in items:
                    self.handle_item(item, now)
                # mark any vehicles that have gone offline as not current
                old_locations = current_locations.exclude(id__in=self.current_location_ids)
                print(old_locations.update(current=False), end='\t', flush=True)
        except (requests.exceptions.RequestException, IntegrityError, TypeError, ValueError) as e:
            print(e)
            logger.error(e, exc_info=True)
            # current_locations.update(current=False)
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
                wait = 0
                print(e)
                logger.error(e, exc_info=True)
            sleep(wait)

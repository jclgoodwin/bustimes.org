import math
import requests
import logging
import sys
from setproctitle import setproctitle
from time import sleep
from django.db import OperationalError, IntegrityError, transaction
from django.core.management.base import BaseCommand
from django.utils import timezone
from ..models import DataSource, VehicleLocation


logger = logging.getLogger(__name__)


def calculate_bearing(a, b):
    if a == b:
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
    if journey.code and latest_location.journey.code != journey.code:
        return False
    if latest_location.current:
        return latest_location.journey.service == journey.service
    if journey.code and latest_location.journey.code == journey.code:
        return True


class ImportLiveVehiclesCommand(BaseCommand):
    session = requests.Session()
    current_location_ids = set()

    def get_items(self):
        response = self.session.get(self.url, timeout=10)
        if response.ok:
            return response.json()
        return ()

    @transaction.atomic
    def handle_item(self, item, now):
        journey, vehicle_created = self.get_journey(item)
        if not journey:
            return
        if vehicle_created:
            latest = None
        else:
            latest = journey.vehicle.latest_location
            if latest and latest.current and latest.journey.source != self.source:
                if latest.journey.service or not journey.service:
                    return  # defer to other source
        location = self.create_vehicle_location(item, journey.vehicle, journey.vehicle)
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
            if journey.service and not latest.journey.service:
                latest.journey.service = journey.service
                latest.journey.save()
            if journey.destination and not latest.journey.destination:
                latest.journey.destination = journey.destination
                latest.journey.save()
            location.journey = latest.journey
            if location.heading is None:
                location.heading = calculate_bearing(latest.latlong, location.latlong)
        else:
            journey.source = self.source
            journey.datetime = location.datetime
            journey.save()
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

    def update(self):
        now = timezone.now()
        self.source, source_created = DataSource.objects.update_or_create(
            {'url': self.url, 'datetime': now},
            name=self.source_name
        )

        self.current_location_ids = set()

        current_locations = VehicleLocation.objects.filter(journey__source=self.source, current=True)

        try:
            for item in self.get_items():
                self.handle_item(item, now)
            # mark any vehicles that have gone offline as not current
            old_locations = current_locations.exclude(id__in=self.current_location_ids)
            print(old_locations.update(current=False), end='\t', flush=True)
        except (requests.exceptions.RequestException, IntegrityError, TypeError, ValueError) as e:
            print(e)
            logger.error(e, exc_info=True)
            current_locations.update(current=False)
            return 120

        return 40

    def handle(self, *args, **options):
        setproctitle(sys.argv[1])
        while True:
            try:
                wait = self.update()
            except OperationalError as e:
                wait = 0
                print(e)
                logger.error(e, exc_info=True)
            sleep(wait)

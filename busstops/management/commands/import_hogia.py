import requests
import logging
from time import sleep
from datetime import timedelta
from django.db import OperationalError, transaction
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from django.utils import timezone
from ...models import DataSource, Vehicle, VehicleLocation, Service


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    @transaction.atomic
    def update(self):
        now = timezone.now()

        url = 'http://ncc.hogiacloud.com/map/VehicleMapService/Vehicles'

        try:
            response = self.session.get(url, timeout=5)
        except requests.exceptions.RequestException as e:
            print(e)
            logger.error(e, exc_info=True)
            sleep(120)  # wait for two minutes
            return

        source = DataSource.objects.update_or_create({'url': url, 'datetime': now}, name='NCC Hogia')[0]
        print(source.vehiclelocation_set.filter(current=True).update(current=False), end='\t', flush=True)

        for item in response.json():
            vehicle = item['Label']
            if ': ' in vehicle:
                vehicle, service = vehicle.split(': ', 1)
                service = service.split('/', 1)[0]
                service = Service.objects.filter(servicecode__scheme=source.name, servicecode__code=service).first()
            else:
                service = None
            vehicle = Vehicle.objects.update_or_create(
                source=source,
                code=item['Label'].split(': ')[0]
            )[0]
            if item['Speed'] != item['Speed']:
                item['Speed'] = None
            latest = vehicle.vehiclelocation_set.last()
            if latest and latest.data == item:
                if service is None and now - latest.datetime > timedelta(minutes=10):
                    continue
                latest.current = True
                latest.save()
            else:
                location = VehicleLocation(
                    datetime=now,
                    vehicle=vehicle,
                    source=source,
                    service=service,
                    latlong=Point(item['Longitude'], item['Latitude']),
                    data=item,
                    current=True
                )
                location.save()
        sleep(10)

    def handle(self, *args, **options):

        self.session = requests.Session()

        while True:
            try:
                self.update()
            except OperationalError as e:
                print(e)
                logger.error(e, exc_info=True)

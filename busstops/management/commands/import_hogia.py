import requests
import logging
from urllib.parse import unquote
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
        url = 'http://ncc.hogiacloud.com/map/VehicleMapService/Vehicles'
        now = timezone.now()

        source, created = DataSource.objects.get_or_create({'url': url, 'datetime': now}, name='NCC Hogia')

        print(source.vehiclelocation_set.filter(current=True).update(current=False), end='\t', flush=True)

        try:
            response = self.session.get(url, timeout=30)
        except requests.exceptions.RequestException as e:
            print(e)
            return 120  # wait for two minutes

        for item in response.json():
            label = item['Label']
            if ': ' in label:
                vehicle, service = label.split(': ', 1)
                service = service.split('/', 1)[0]
            else:
                service = None
            vehicle = Vehicle.objects.update_or_create(
                source=source,
                code=label.split(': ')[0]
            )[0]
            label = label.split()
            if len(label) == 3:
                early = int(unquote(label[2]))
            else:
                early = None
            if item['Speed'] != item['Speed']:
                item['Speed'] = None
            latest = vehicle.vehiclelocation_set.last()
            if latest and latest.data == item:
                if service is None and now - latest.datetime > timedelta(minutes=10):
                    continue
                latest.current = True
                latest.save()
            else:
                if service:
                    try:
                        service = Service.objects.get(servicecode__scheme=source.name, servicecode__code=service)
                    except (Service.DoesNotExist, Service.MultipleObjectsReturned) as e:
                        print(e, service)
                        service = None
                location = VehicleLocation(
                    datetime=now,
                    vehicle=vehicle,
                    source=source,
                    service=service,
                    latlong=Point(item['Longitude'], item['Latitude']),
                    data=item,
                    current=True,
                    early=early,
                    heading=item['Direction']
                )
                location.save()
        return 10

    def handle(self, *args, **options):

        self.session = requests.Session()

        while True:
            try:
                wait = self.update()
            except OperationalError as e:
                print(e)
                logger.error(e, exc_info=True)
            sleep(wait)

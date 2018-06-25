import requests
import logging
import pytz
import ciso8601
from time import sleep
from django.db import OperationalError, transaction
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from django.utils import timezone
from ...models import DataSource, Vehicle, VehicleLocation, Service, Operator


logger = logging.getLogger(__name__)
LOCAL_TIMEZONE = pytz.timezone('Europe/London')


class Command(BaseCommand):
    @transaction.atomic
    def update(self):
        now = timezone.now()

        url = 'http://rtl2.ods-live.co.uk/api/vehiclePositions'

        try:
            response = self.session.get(url, timeout=5)
        except requests.exceptions.RequestException as e:
            print(e)
            logger.error(e, exc_info=True)
            sleep(120)  # wait for two minutes
            return

        source = DataSource.objects.update_or_create({'url': url, 'datetime': now}, name='Reading')[0]
        print(source.vehiclelocation_set.filter(current=True).update(current=False), end='\t', flush=True)

        for item in response.json():
            vehicle = item['vehicle']
            vehicle, created = Vehicle.objects.update_or_create(
                source=source,
                code=vehicle,
                operator=Operator.objects.get(name='Reading Buses')
            )
            try:
                service = vehicle.operator.service_set.get(current=True, line_name__iexact=item['service'])
            except Service.DoesNotExist:
                print(item)
                service = None
            if created:
                latest = None
            else:
                latest = vehicle.vehiclelocation_set.last()
            if latest and latest.data == item:
                latest.current = True
                latest.save()
            else:
                location = VehicleLocation(
                    datetime=ciso8601.parse_datetime(item['observed']).astimezone(LOCAL_TIMEZONE),
                    vehicle=vehicle,
                    source=source,
                    service=service,
                    latlong=Point(float(item['longitude']), float(item['latitude'])),
                    data=item,
                    current=True
                )
                location.save()

    def handle(self, *args, **options):

        self.session = requests.Session()

        while True:
            try:
                self.update()
            except OperationalError as e:
                print(e)
                logger.error(e, exc_info=True)
            sleep(40)

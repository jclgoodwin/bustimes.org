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

        reading = Operator.objects.get(name='Reading Buses')
        thames = Operator.objects.get(name='Thames Valley Buses')
        kennections = Operator.objects.get(name='Kennections')
        green_line = Operator.objects.get(id='GLRB')

        for item in response.json():
            service = item['service'].lower()
            operator = reading
            if service.startswith('tv'):
                operator = thames
                service = service[2:]
            elif service.startswith('k'):
                if service != 'k102':
                    operator = kennections
                service = service[1:]
            elif service == '702' or service == '703':
                operator = green_line

            vehicle = item['vehicle']
            vehicle, created = Vehicle.objects.update_or_create(
                {'operator': operator},
                source=source,
                code=vehicle
            )

            if created:
                latest = None
            else:
                latest = vehicle.vehiclelocation_set.last()
            if latest and latest.data == item:
                latest.current = True
                latest.save()
            else:
                try:
                    if service:
                        service = operator.service_set.get(current=True, line_name__iexact=service)
                    else:
                        service = None
                except Service.DoesNotExist:
                    print(operator, service)
                    service = None
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
            except (TypeError, OperationalError, ValueError) as e:
                print(e)
                logger.error(e, exc_info=True)
            sleep(40)

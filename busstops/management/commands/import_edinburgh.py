import requests
import logging
from time import sleep
from django.db import OperationalError, transaction
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from django.utils import timezone
from ...models import DataSource, Vehicle, VehicleLocation, Service


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    url = 'https://tfeapp.com/live/vehicles.php'
    operators = ('LOTH', 'EDTR', 'ECBU', 'NELB')

    @transaction.atomic
    def update(self):
        now = timezone.now()

        source, created = DataSource.objects.get_or_create({'url': self.url, 'datetime': now}, name='TfE')

        if not created:
            print(source.vehiclelocation_set.filter(current=True).update(current=False), end='\t', flush=True)

        try:
            response = self.session.get(self.url, timeout=30)
        except requests.exceptions.RequestException as e:
            print(e)
            return 120  # wait for two minutes

        for item in response.json():
            vehicle = item['vehicle_id']
            vehicle, created = Vehicle.objects.update_or_create(
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
                    service = Service.objects.get(operator__in=self.operators, line_name=item['service_name'],
                                                  current=True)
                except (Service.DoesNotExist, Service.MultipleObjectsReturned) as e:
                    print(e, item['service_name'])
                if service and not vehicle.operator:
                    vehicle.operator = service.operator.first()
                    vehicle.save()
                location = VehicleLocation(
                    datetime=now,
                    vehicle=vehicle,
                    source=source,
                    service=service,
                    latlong=Point(item['longitude'], item['latitude']),
                    data=item,
                    current=True
                )
                location.save()
        return 30

    def handle(self, *args, **options):

        self.session = requests.Session()

        while True:
            try:
                wait = self.update()
            except (OperationalError, ValueError) as e:
                print(e)
                logger.error(e, exc_info=True)
                wait = 30
            sleep(wait)

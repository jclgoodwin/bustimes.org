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
    url = 'http://api.otrl-bus.io/api/bus/nearby'

    def get_items(self):
        for opco, lat, lng in (
            ('eastangliabuses', 52.6, 1.3),
            ('eastangliabuses', 52.6458, 1.1162),
            ('eastangliabuses', 52.6816, 0.9378),
            ('eastangliabuses', 52.4593, 1.5661),
            ('eastangliabuses', 52.8313, 0.8393),
            ('eastangliabuses', 52.7043, 1.4073),
            ('brightonhove', 51, -0.1372),
            ('brightonhove', 50.6, -0.1372),
            ('brightonhove', 50.8225, -0.1372),
            ('brightonhove', 50.8225, -0.2),
            ('brightonhove', 50.8225, 0),
            ('oxford', 51.752, -1.2577),
            ('oxford', 51.752, -1.3),
            ('oxford', 51.752, -1.4),
            ('oxford', 51.6, -1.3),
            ('oxford', 51.8, -1.4),
            ('oxford', 51.752, -1.0577),
            ('oxford', 51.752, -0.9),
            ('gonortheast', 54.9783, -1.6178),
        ):
            sleep(2)
            response = self.session.get(self.url, params={'lat': lat, 'lng': lng}, timeout=30, headers={'opco': opco})
            print(len(response.json()['data']), response.url, opco)
            for item in response.json()['data']:
                yield item

    @transaction.atomic
    def update(self):
        now = timezone.now()

        source, created = DataSource.objects.get_or_create({'url': self.url, 'datetime': now}, name='GOEA')

        if not created:
            print(source.vehiclelocation_set.filter(current=True).update(current=False), end='\t', flush=True)

        return 0
        try:
            items = list(self.get_items())
        except requests.exceptions.RequestException as e:
            print(e)
            return 120  # wait for two minutes

        for item in items:
            vehicle = item['vehicleRef']
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
                if item['vehicleRef'][:5] == 'GOEA-':
                    operators = ('KCTB',)
                elif item['vehicleRef'][:5] == 'CSLB-':
                    operators = ('OXBC', 'THTR')
                elif item['vehicleRef'][:4] == 'GNE-':
                    operators = ('GNEL',)
                elif item['vehicleRef'][:3] == 'BH-':
                    operators = ('BHBC',)
                else:
                    operators = ()
                try:
                    service = Service.objects.get(operator__in=operators, line_name=item['lineRef'], current=True)
                except (Service.DoesNotExist, Service.MultipleObjectsReturned) as e:
                    service = None
                    print(e, item)
                if service and service.operator.first() != vehicle.operator:
                    vehicle.operator = service.operator.first()
                    vehicle.save()
                location = VehicleLocation(
                    datetime=item['recordedTime'],
                    vehicle=vehicle,
                    source=source,
                    service=service,
                    latlong=Point(item['geo']['longitude'], item['geo']['latitude']),
                    data=item,
                    current=True,
                    heading=item['geo']['bearing']
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

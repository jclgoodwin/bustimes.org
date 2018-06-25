import requests
import logging
from time import sleep
from django.db import OperationalError, transaction
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from django.utils import timezone
from ...models import DataSource, VehicleLocation, Service


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    @transaction.atomic
    def update(self):
        now = timezone.now()

        url = 'http://app.arrivabus.co.uk/journeyplanner/query/eny'
        source = DataSource.objects.update_or_create({'url': url, 'datetime': now}, name='Arriva')[0]
        print(source.vehiclelocation_set.filter(current=True, source=source).update(current=False),
              end='\t', flush=True)

        for minx, maxx in (
            (-5000000, -4000000),
            (-4000000, -3000000),
            (-3000000, -2000000),
            (-2000000, -1000000),
            (-1000000, 0),
            (0, 1000000),
        ):

            params = {
                'look_minx': minx,
                'look_maxx': maxx,
                'look_miny': 0,
                'look_maxy': 60000000,
                'tpl': 'trains2json',
                'performLocating': 1
            }

            try:
                response = self.session.get(url, params=params, timeout=5)
                print(response.url)
            except requests.exceptions.RequestException as e:
                print(e)
                logger.error(e, exc_info=True)
                sleep(120)  # wait for two minutes
                return

            for item in response.json()['look']['trains']:
                latlong = Point(int(item['x']) / 1000000, int(item['y']) / 1000000)
                print(item)
                service = item['name'].split()[-1]
                service = Service.objects.filter(line_name=service, operator__name__startswith='Arriva', current=True)
                service = service.first()
                location = VehicleLocation(
                    service=service,
                    datetime=now,
                    source=source,
                    data=item,
                    latlong=latlong,
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
            sleep(10)

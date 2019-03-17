import yaml
import os
from django.conf import settings
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import GEOSGeometry
from ...models import StopPoint


DIR = os.path.dirname(__file__)


class Command(BaseCommand):
    def handle(self, *args, **options):
        with open(os.path.join(settings.DATA_DIR, 'stops.yaml')) as open_file:
            records = yaml.load(open_file, Loader=yaml.FullLoader)
            for atco_code, record in records.items():
                if 'latlong' in record:
                    record['latlong'] = GEOSGeometry(record['latlong'])
                StopPoint.objects.filter(atco_code=atco_code).update(**record)

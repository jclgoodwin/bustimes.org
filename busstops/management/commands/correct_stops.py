import yaml
from django.conf import settings
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import GEOSGeometry
from ...models import StopPoint


class Command(BaseCommand):
    def handle(self, *args, **options):
        with open(settings.BASE_DIR / 'fixtures' / 'stops.yaml') as open_file:
            records = yaml.load(open_file, Loader=yaml.BaseLoader)
            for atco_code, record in records.items():
                if 'latlong' in record:
                    record['latlong'] = GEOSGeometry(record['latlong'])
                StopPoint.objects.filter(atco_code=atco_code).update(**record)

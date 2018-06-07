import yaml
import os
from django.conf import settings
from django.core.management.base import BaseCommand
from ...models import StopPoint


DIR = os.path.dirname(__file__)


class Command(BaseCommand):
    def handle(self, *args, **options):
        with open(os.path.join(settings.DATA_DIR, 'stops.yaml')) as open_file:
            records = yaml.load(open_file)
            for atco_code in records:
                StopPoint.objects.filter(atco_code=atco_code).update(**records[atco_code])

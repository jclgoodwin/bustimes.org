import os
import zipfile
import csv
from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings
from ...models import Service


def get_service(row):
    for region in 'EA', 'EM', 'WM', 'SE', 'SW':
        col = 'TNDS-' + region
        if row[col]:
            return Service.objects.filter(region=region, service_code__endswith=''.join(row[col].split('-')[:-1]))
    for region in 'S', 'Y', 'NE', 'W':
        col = 'TNDS-' + region
        if row[col]:
            return Service.objects.filter(region=region, service_code=row[col])
    if row['TNDS-NW']:
        return Service.objects.filter(region=region, service_code__endswith=''.join(row['TNDS-NW'].split('_')[:-1]))


def handle_file(open_file):
    for row in csv.DictReader(line.decode() for line in open_file):
        service = get_service(row)
        if service:
            if row['HighFloor'] == 'LF':
                low_floor = True
            elif row['HighFloor'] == 'HF':
                low_floor = False
            else:
                low_floor = None
            service.update(wheelchair=row['Wheelchair Access'] == 'TRUE',
                           low_floor=low_floor,
                           assistance_service=row['Assistance Service'] == 'TRUE',
                           mobility_scooter=row['MobilityScooter'] == 'TRUE')


class Command(BaseCommand):
    @transaction.atomic
    def handle(self, *args, **options):
        path = os.path.join(settings.DATA_DIR, 'accessibility-data.zip')
        with zipfile.ZipFile(path) as archive:
            for path in archive.namelist():
                if 'IF145' in path:
                    with archive.open(path, 'r') as open_file:
                        handle_file(open_file)

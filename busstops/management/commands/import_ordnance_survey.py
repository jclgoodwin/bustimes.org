import os
import zipfile
import csv
from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.gis.geos import Point, Polygon
from django.utils import timezone
from busstops.models import Locality, DataSource, Place


class Command(BaseCommand):
    shit_types = {'Postcode', 'Section Of Named Road', 'Named Road', 'Numbered Road', 'Section Of Numbered Road'}

    def handle_file(self, open_file):
        source = DataSource.objects.update_or_create(name='Ordnance Survey', defaults={'datetime': timezone.now()})[0]
        lines = (line.decode() for line in open_file)
        for row in csv.DictReader(lines, fieldnames=self.fieldnames):
            local_type = row['LOCAL_TYPE']
            if row['NAME1_LANG'] != 'eng' and row['NAME2'] and row['NAME2_LANG'] == 'eng':
                name = row['NAME2']
            else:
                name = row['NAME1']
            if local_type not in self.shit_types and not Locality.objects.filter(name=name).exists():
                print(row['LOCAL_TYPE'], row['NAME1'])
                polygon = Polygon.from_bbox((row['MBR_XMIN'], row['MBR_YMIN'], row['MBR_XMAX'], row['MBR_YMAX']))
                polygon.srid = 27700
                Place.objects.update_or_create(name=row['NAME1'], source=source, code=row['ID'], defaults={
                    'latlong': Point(float(row['GEOMETRY_X']), float(row['GEOMETRY_Y']), srid=27700),
                    'polygon': polygon
                })

    def handle(self, *args, **options):
        path = os.path.join(settings.DATA_DIR, 'opname_csv_gb.zip')
        with zipfile.ZipFile(path) as archive:
            with archive.open(os.path.join('DOC', 'OS_Open_Names_Header.csv'), 'r') as open_file:
                self.fieldnames = open_file.read().decode('utf-8-sig').strip().split(',')
            for path in archive.namelist():
                if path.startswith('DATA') and path.endswith('.csv'):
                    with archive.open(path, 'r') as open_file:
                        self.handle_file(open_file)

"""
Usage:

    $ ./manage.py import_stop_areas < StopAreas.py
"""

import sys
import csv

from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from busstops.models import StopArea, AdminArea

class Command(BaseCommand):

    def handle(self, *args, **options):
        reader = csv.reader(sys.stdin)
        next(reader, None) # skip past header
        for row in reader:
            try:
                StopArea.objects.get_or_create(
                    id=row[0],
                    name=row[1],
                    admin_area=AdminArea.objects.get(id=row[3]),
                    stop_area_type=row[4],
                    location=Point(6, 7),
                    active=(row[12] == 'act'),
                    )
            except UnicodeDecodeError:
                print row

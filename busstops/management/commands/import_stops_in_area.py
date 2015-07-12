"""
Usage:

    $ ./manage.py import_stops_in_area < StopsInArea.csv
"""

import sys
import csv

from django.core.management.base import BaseCommand
from busstops.models import StopPoint, StopArea

class Command(BaseCommand):

    def handle(self, *args, **options):
        reader = csv.reader(sys.stdin)
        next(reader, None) # skip past header
        area = None
        for row in reader:
            try:
                if area is None or area.id != row[0]:
                    area = StopArea.objects.get(id=row[0])
                stop = StopPoint.objects.get(atco_code=row[1])
                stop.stop_area = area
                stop.save()
            except:
                print row

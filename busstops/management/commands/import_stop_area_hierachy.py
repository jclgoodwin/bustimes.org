"""
Usage:

    $ ./manage.py import_stop_area_hierachy < AreaHierachy.py
"""

import sys
import csv

from django.core.management.base import BaseCommand
from busstops.models import StopArea

class Command(BaseCommand):

    def handle(self, *args, **options):
        reader = csv.reader(sys.stdin)
        next(reader, None) # skip past header
        for row in reader:
            print row
            parent = StopArea.objects.get(id=row[0])
            child = StopArea.objects.get(id=row[0])
            child.parent = parent
            child.save()

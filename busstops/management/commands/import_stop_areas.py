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

    @staticmethod
    def row_to_stoparea(row):
        """
        Given a CSV row (a list of strings),
        returns a StopArea object.
        """
        return StopArea(
            id=row[0],
            name=row[1].decode('latin1'),
            admin_area=AdminArea.objects.get(id=row[3]),
            stop_area_type=row[4],
            location=Point(int(row[6]), int(row[7]), srid=27700),
            active=(row[12] == 'act'),
            )

    def handle(self, *args, **options):
        reader = csv.reader(sys.stdin)
        next(reader, None) # skip past header
        for row in reader:
            try:
                stoparea = self.row_to_stoparea(row)
                stoparea.save()
            except UnicodeDecodeError:
                print row

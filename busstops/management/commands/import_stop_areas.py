"""
Usage:

    $ ./manage.py import_stop_areas < StopAreas.py
"""

import sys
import csv

from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from django.utils.encoding import smart_text
from busstops.models import StopArea, AdminArea

class Command(BaseCommand):

    @staticmethod
    def row_to_stoparea(row):
        """
        Given a CSV row (a list of strings),
        creates a StopArea object in the database if it doesn't exist,
        and returns an (area, created) tuple.
        """
        return StopArea.objects.get_or_create(
            id=row[0],
            name=smart_text(row[1]),
            admin_area=AdminArea.objects.get(id=row[3]),
            stop_area_type=row[4],
            location=Point(6, 7),
            active=(row[12] == 'act'),
            )

    def handle(self, *args, **options):
        reader = csv.reader(sys.stdin)
        next(reader, None) # skip past header
        for row in reader:
            try:
                self.row_to_stoparea(row)
            except UnicodeDecodeError:
                print row

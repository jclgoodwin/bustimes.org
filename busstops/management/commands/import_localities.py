"""
Import localities from the NPTG.

Usage:

    import_localities < Localities.csv
"""

import sys
import csv
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from busstops.models import Locality, AdminArea, District


class Command(BaseCommand):

    def handle(self, *args, **options):
        reader = csv.reader(sys.stdin)
        next(reader) # skip past header
        for row in reader:
            locality = Locality(
                id=row[0],
                name=row[1],
                qualifier_name=row[5],
                admin_area=AdminArea.objects.get(id=row[9]),
                location=Point(map(int, (row[13], row[14])), srid=27700),
                )
            if row[10] != '310': # bogus value for nonexistent districts
                locality.district = District.objects.get(id=row[10])
            locality.save()

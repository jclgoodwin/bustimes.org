"""
Import administrative areas from the NPTG.

Usage:

    import_areas < AdminAreas.csv
"""
import sys
import csv

from django.core.management.base import BaseCommand

from busstops.models import Region, AdminArea

class Command(BaseCommand):

    def handle(self, *args, **options):
        reader = csv.reader(sys.stdin)
        next(reader) # skip past header row
        for row in reader:
            AdminArea.objects.create(
                id=row[0],
                atco_code=row[1],
                name=row[2],
                short_name=row[4],
                country=row[6],
                region=Region.objects.get(id=row[7]),
                )

"""
Import districts from the NPTG.

Usage:

    import_districts > Districts.csv
"""
import sys
import csv

from django.core.management.base import BaseCommand

from busstops.models import District, AdminArea

class Command(BaseCommand):

    def handle(self, *args, **options):
        reader = csv.reader(sys.stdin)
        next(reader) # skip past header
        for row in reader:
            District.objects.create(
                id=row[0],
                name=row[1],
                admin_area=AdminArea.objects.get(id=row[3]),
                )

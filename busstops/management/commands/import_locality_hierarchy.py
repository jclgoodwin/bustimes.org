"""
Add hierarchies to localities imported from the NPTG.

Usage:

    import_locality_hierarchy < LocalityHierarchy.csv
"""
import sys
import csv
from django.core.management.base import BaseCommand
from busstops.models import Locality


class Command(BaseCommand):

    def handle(self, *args, **options):
        reader = csv.reader(sys.stdin)
        next(reader) # skip past header
        for row in reader:
            parent = Locality.objects.get(id=row[0])
            child = Locality.objects.get(id=row[1])
            child.parent = parent
            child.save()

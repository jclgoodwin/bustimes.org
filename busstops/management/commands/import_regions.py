"""
Import regions from the NPTG.

Usage:

    ./manage.py import_regions < Regions.csv
"""
import sys
import csv
from django.core.management.base import BaseCommand
from busstops.models import Region


class Command(BaseCommand):

    def handle(self, *args, **options):
        reader = csv.reader(sys.stdin)
        next(reader) # skip past header
        for row in reader:
            Region.objects.create(id=row[0], name=row[1])

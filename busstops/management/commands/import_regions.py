"""
Import regions from the NPTG.

Usage:

    ./manage.py import_regions < Regions.csv
"""

from busstops.management.import_from_csv import ImportFromCSVCommand
from busstops.models import Region


class Command(ImportFromCSVCommand):

    def handle_row(self, row):
        Region.objects.update_or_create(
            id=row['RegionCode'],
            defaults={
                'name': row['RegionName']
            }
        )

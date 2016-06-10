"""
Import regions from the NPTG.

Usage:

    ./manage.py import_regions < Regions.csv
"""

from ..import_from_csv import ImportFromCSVCommand
from ...models import Region


class Command(ImportFromCSVCommand):

    def handle_row(self, row):
        return Region.objects.update_or_create(
            id=row['RegionCode'],
            defaults={
                'name': row['RegionName']
            }
        )

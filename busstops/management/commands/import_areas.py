"""
Import administrative areas from the NPTG.

Usage:

    import_areas < AdminAreas.csv
"""

from busstops.management.import_from_csv import ImportFromCSVCommand
from busstops.models import Region, AdminArea


class Command(ImportFromCSVCommand):

    def handle_row(self, row):
        AdminArea.objects.update_or_create(
            id=row['AdministrativeAreaCode'],
            defaults={
                'atco_code':  row['AtcoAreaCode'],
                'name':       row['AreaName'],
                'short_name': row['ShortName'],
                'country':    row['Country'],
                'region':     Region.objects.get(id=row['RegionCode']),
            }
        )

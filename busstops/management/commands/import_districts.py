"""
Import districts from the NPTG.

Usage:

    import_districts > Districts.csv
"""

from busstops.management.import_from_csv import ImportFromCSVCommand
from busstops.models import District


class Command(ImportFromCSVCommand):

    def handle_row(self, row):
        District.objects.update_or_create(
            id=row['DistrictCode'],
            defaults={
                'name': row['DistrictName'].replace('\'', u'\u2019'),
                'admin_area_id': row['AdministrativeAreaCode'],
            }
        )

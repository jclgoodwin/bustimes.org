"""
Usage:

    import_localities < Localities.csv
"""

from django.contrib.gis.geos import Point
from ..import_from_csv import ImportFromCSVCommand
from ...models import Locality


class Command(ImportFromCSVCommand):
    """
    Imports localities from the NPTG
    """
    def handle_row(self, row):
        defaults = {
            'name': row['LocalityName'].replace('\'', '\u2019'),
            'qualifier_name': row['QualifierName'],
            'admin_area_id': row['AdministrativeAreaCode'],
            'latlong': Point(int(row['Easting']), int(row['Northing']), srid=27700),
        }

        if row['NptgDistrictCode'] != '310':
            defaults['district_id'] = row['NptgDistrictCode']

        Locality.objects.update_or_create(
            id=row['NptgLocalityCode'],
            defaults=defaults
        )

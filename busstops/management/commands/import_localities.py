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
    def handle_rows(self, rows):
        existing_localities = Locality.objects.in_bulk()
        to_update = []
        to_create = []

        for row in rows:
            locality_code = row['NptgLocalityCode']
            if locality_code in existing_localities:
                locality = existing_localities[locality_code]
            else:
                locality = Locality()

            locality.name = row['LocalityName'].replace('\'', '\u2019')
            locality.qualifier_name = row['QualifierName']
            locality.admin_area_id = row['AdministrativeAreaCode']
            locality.latlong = Point(int(row['Easting']), int(row['Northing']), srid=27700)

            if row['NptgDistrictCode'] != '310':
                locality.district_id = row['NptgDistrictCode']

            if locality.id:
                to_update.append(locality)
            else:
                locality.id = locality_code
                to_create.append(locality)

        Locality.objects.bulk_update(to_update, fields=['name', 'qualifier_name', 'admin_area', 'latlong', 'district'])
        Locality.objects.bulk_create(to_create)

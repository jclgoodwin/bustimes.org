"""
Import localities from the NPTG.

Usage:

    import_localities < Localities.csv
"""

from busstops.management.import_from_csv import ImportFromCSVCommand
from busstops.models import Locality, AdminArea, District
from django.contrib.gis.geos import Point


class Command(ImportFromCSVCommand):

    def handle_row(self, row):

        defaults = {
            'name':           row['LocalityName'].replace('\'', '’'),
            'qualifier_name': row['QualifierName'],
            'admin_area':     AdminArea.objects.get(id=row['AdministrativeAreaCode']),
            'location':       Point(int(row['Easting']), int(row['Northing']), srid=27700),
        }

        if row['NptgDistrictCode'] != '310':
            defaults['district'] = District.objects.get(id=row['NptgDistrictCode'])

        Locality.objects.update_or_create(
            id=row['NptgLocalityCode'],
            defaults=defaults
        )

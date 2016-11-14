"""
Usage:

    ./manage.py import_ni_stops < bus-stop-list-february-2016.csv
"""

from django.contrib.gis.geos import Point
from ..import_from_csv import ImportFromCSVCommand
from ...models import StopPoint


class Command(ImportFromCSVCommand):
    """
    Imports Northern Irish bus stops
    """
    def handle_row(self, row):
        defaults = {
            'latlong': Point(
                float(row['Longitude']),
                float(row['Latitude']),
                srid=4326  # World Geodetic System
            ),
            'common_name': row['Stop_Name'],
            'locality_centre': False,
            'active': True,
            'indicator': row['ServiceDirection'].lower()
        }
        StopPoint.objects.update_or_create(atco_code=row['PTI_REF_GIS'], defaults=defaults)

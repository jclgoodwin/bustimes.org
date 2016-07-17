"""
Usage:

    ./manage.py import_ni_stops < bus-stop-list-february-2016.csv
"""

from ..import_from_csv import ImportFromCSVCommand
from ...models import StopPoint, Locality, AdminArea
from django.contrib.gis.geos import Point


class Command(ImportFromCSVCommand):

    def handle_row(self, row):
        defaults = {
            'latlong': Point(
                float(row['Longitude']),
                float(row['Latitude']),
                srid=4326
            ),
            'common_name': row['Stop_Name'].decode('utf-8', 'replace'),
            'locality_centre': False,
            'active': True,
            'indicator': row['ServiceDirection'].lower()
        }
        StopPoint.objects.update_or_create(atco_code=row['PTI_REF_GIS'], defaults=defaults)

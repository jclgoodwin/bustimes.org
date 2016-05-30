"""
Usage:

    ./manage.py import_stops < Stops.csv
"""

from ..import_from_csv import ImportFromCSVCommand
from ...models import StopPoint
from django.contrib.gis.geos import Point


class Command(ImportFromCSVCommand):

    def handle_row(self, row):
        defaults = {
            'locality_id': row['NptgLocalityCode'],
            'latlong': Point(
                float(row['Longitude']),
                float(row['Latitude']),
                srid=4326
            ),
            'locality_centre': (row['LocalityCentre'] == '1'),
            'active': (row['Status'] == 'act'),
            'admin_area_id': row['AdministrativeAreaCode']
        }
        for django_field_name, naptan_field_name in self.field_names:
            defaults[django_field_name] = unicode(row[naptan_field_name], errors='ignore')

        StopPoint.objects.update_or_create(atco_code=row['AtcoCode'], defaults=defaults)

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)

        django_field_names = (
            'naptan_code',
            'common_name',
            'landmark',
            'street',
            'crossing',
            'indicator',
            'suburb',
            'stop_type',
            'bus_stop_type',
            'timing_status',
            'town',
            'bearing',
        )
        # A list of tuples like ('naptan_code', 'NaptanCode')
        self.field_names = [(name, self.to_camel_case(name)) for name in django_field_names]

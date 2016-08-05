"""
Usage:

    ./manage.py import_stops < Stops.csv
"""

from django.contrib.gis.geos import Point
from titlecase import titlecase
from . import clean_stops
from ..import_from_csv import ImportFromCSVCommand
from ...models import StopPoint


INDICATORS_TO_PROPER_CASE = {
    indicator.lower(): indicator for indicator in clean_stops.INDICATORS_TO_PROPER_CASE
}


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
            value = row[naptan_field_name].strip()
            if django_field_name in ('street', 'crossing', 'landmark'):
                if value in ('-', '--', '---', '*', 'TBA', 'unknown'):
                    value = ''
                elif value.isupper():
                    value = titlecase(value)
            defaults[django_field_name] = value

        if defaults.get('indicator') in clean_stops.INDICATORS_TO_REPLACE:
            defaults['indicator'] = clean_stops.INDICATORS_TO_REPLACE.get(
                defaults['indicator']
            )
        elif defaults['indicator'].lower() in INDICATORS_TO_PROPER_CASE:
            defaults['indicator'] = INDICATORS_TO_PROPER_CASE.get(
                defaults['indicator'].lower()
            )

        StopPoint.objects.update_or_create(atco_code=row['ATCOCode'], defaults=defaults)

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

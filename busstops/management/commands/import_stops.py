"""Usage:

    ./manage.py import_stops < Stops.csv
"""

from django.contrib.gis.geos import Point
from titlecase import titlecase
from ..import_from_csv import ImportFromCSVCommand
from ...models import Locality, StopPoint


INDICATORS_TO_PROPER_CASE = {indicator.lower(): indicator for indicator in (
    'opp',
    'adj',
    'at',
    'nr',
    'on',
    'o/s',
    'in',
    'behind',
    'before',
    'after',
    'N-bound',
    'NE-bound',
    'E-bound',
    'SE-bound',
    'S-bound',
    'SW-bound',
    'W-bound',
    'NW-bound',
)}

INDICATORS_TO_REPLACE = {
    'opp.': 'opp',
    'opposite': 'opp',
    'adjacent': 'adj',
    'near': 'nr',
    'before ': 'before',
    'outside': 'o/s',
    'os': 'o/s',
    'n bound': 'N-bound',
    'n - bound': 'N-bound',
    'ne bound': 'NE-bound',
    'ne - bound': 'NE-bound',
    'e bound': 'E-bound',
    'e - bound': 'E-bound',
    'se bound': 'SE-bound',
    'se - bound': 'SE-bound',
    's bound': 'S-bound',
    's - bound': 'S-bound',
    'sw bound': 'SW-bound',
    'sw - bound': 'SW-bound',
    'w bound': 'W-bound',
    'w - bound': 'W-bound',
    'nw bound': 'NW-bound',
    'nw - bound': 'NW-bound',
    'nb': 'N-bound',
    'eb': 'E-bound',
    'sb': 'S-bound',
    'wb': 'W-bound',
    'northbound': 'N-bound',
    'north bound': 'N-bound',
    'northeastbound': 'NE-bound',
    'north east bound': 'NE-bound',
    'eastbound': 'E-bound',
    'east-bound': 'E-bound',
    'east bound': 'E-bound',
    'south east bound': 'SE-bound',
    'southbound': 'S-bound',
    'south bound': 'S-bound',
    'south west bound': 'SW-bound',
    'wbound': 'W-bound',
    'westbound': 'W-bound',
    'west bound': 'W-bound',
    'nwbound': 'NW-bound',
    'northwestbound': 'NW-bound',
    'northwest bound': 'NW-bound',
    'north west bound': 'NW-bound',
}


class Command(ImportFromCSVCommand):
    input = 0
    encoding = 'windows-1252'

    def handle_row(self, row):
        defaults = {
            'locality_centre': (row['LocalityCentre'] == '1'),
            'active': (row.get('Status', 'act') == 'act'),
            'admin_area_id': row.get('AdministrativeAreaCode') or row['AdministrativeAreaRef']
        }

        if row['Longitude']:
            defaults['latlong'] = Point(
                float(row['Longitude']),
                float(row['Latitude']),
                srid=4326  # World Geodetic System
            )

        if 'NptgLocalityCode' in row:
            defaults['locality_id'] = row['NptgLocalityCode']
        elif row['NptgLocalityRef']:
            defaults['locality_id'] = row['NptgLocalityRef']
            if not Locality.objects.filter(pk=defaults['locality_id']).exists():
                Locality.objects.create(pk=defaults['locality_id'], admin_area_id=defaults['admin_area_id'])

        for django_field_name, naptan_field_name in self.field_names:
            if naptan_field_name not in row:
                naptan_field_name += '_lang_en'
            if naptan_field_name not in row:
                continue
            value = row[naptan_field_name].strip()
            if django_field_name in ('street', 'crossing', 'landmark', 'indicator', 'common_name'):
                if value.lower() in ('-', '--', '---', '*', 'tba', 'unknown', 'n/a',
                                     'data unavailable'):
                    value = ''
                elif value.isupper() and value != 'YMCA':
                    value = titlecase(value)
            defaults[django_field_name] = value.replace('`', '\'')  # replace backticks

        if defaults.get('indicator').lower() in INDICATORS_TO_REPLACE:
            defaults['indicator'] = INDICATORS_TO_REPLACE.get(
                defaults['indicator'].lower()
            )
        elif defaults['indicator'].lower() in INDICATORS_TO_PROPER_CASE:
            defaults['indicator'] = INDICATORS_TO_PROPER_CASE.get(
                defaults['indicator'].lower()
            )
        elif defaults['indicator'].startswith('220'):
            defaults['indicator'] = ''

        if defaults['stop_type'] == 'class_undefined':
            defaults['stop_type'] = ''
        if defaults['bus_stop_type'] == 'type_undefined':
            defaults['bus_stop_type'] = ''

        if 'CompassPoint' in row:
            defaults['bearing'] = row['CompassPoint']

        atco_code = row.get('ATCOCode') or row['AtcoCode']
        StopPoint.objects.update_or_create(atco_code=atco_code, defaults=defaults)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

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

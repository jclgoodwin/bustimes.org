"""Usage:

    ./manage.py import_maneo_stops < Manéo\ Points\ d\'arrêt\ des\ lignes\ régulières.csv
"""

from titlecase import titlecase
from ..import_from_csv import ImportFromCSVCommand
from ...models import StopPoint


class Command(ImportFromCSVCommand):
    encoding = 'utf-8-sig'

    def handle_row(self, row):
        atco_code = 'maneo-' + row['CODE']
        defaults = {
            'locality_centre': False,
            'active': True,
            'latlong': row['geometry']
        }

        name = row['\ufeffAPPCOM']
        name_parts = name.split(' - ', 1)
        if len(name_parts) == 2:
            if name_parts[1].startswith('Desserte'):
                name = name_parts[0]
                defaults['indicator'] = name_parts[1]
            else:
                defaults['town'] = titlecase(name_parts[1])

        defaults['common_name'] = titlecase(name)

        StopPoint.objects.update_or_create(atco_code=atco_code, defaults=defaults)

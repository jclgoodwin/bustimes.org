"""Usage:

    ./manage.py import_ie_naptan_csv < naptansept2012p20120911-1428.csv
"""

from django.contrib.gis.geos import Point
from ..import_from_csv import ImportFromCSVCommand
from ...models import Locality, StopPoint


class Command(ImportFromCSVCommand):
    @staticmethod
    def handle_row(row):
        admin_area_id = row['NaPTANId'][:3]

        if not admin_area_id:
            return

        if not Locality.objects.filter(id=row['Locality number']).exists():
            locality = Locality(
                id=row['Locality number'],
                name=row['Locality'],
                admin_area_id=admin_area_id
            )
            if '(' in locality.name:
                locality.qualifier_name = locality.name[locality.name.index('(') + 1:-1]
                locality.name = locality.name[:locality.name.index('(')].strip()
            locality.save()

        defaults = dict(
            admin_area_id=admin_area_id,
            locality_id=row['Locality number'],
            stop_type=row['NaPTAN stop class'],
            active=True,
            locality_centre=False
        )

        stop = StopPoint.objects.filter(atco_code=row['NaPTANId']).first()

        if stop:
            if not stop.indicator:
                defaults['indicator'] = row['Code']
        else:
            defaults['indicator'] = row['Code']
            defaults['common_name'] = row['Name without locality']
            if len(defaults['common_name']) > 48:
                print(row)
                return
        if row['Easting']:
            defaults['latlong'] = Point(
                int(row['Easting']),
                int(row['Northing']),
                srid=2157  # Irish Transverse Mercator
            )
        else:
            print(row)
            return

        StopPoint.objects.update_or_create(atco_code=row['NaPTANId'], defaults=defaults)

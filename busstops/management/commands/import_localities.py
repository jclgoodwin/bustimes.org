"""
Usage:

    import_localities < Localities.csv
"""
from ciso8601 import parse_datetime
from django.utils.timezone import make_aware
from django.contrib.gis.geos import GEOSGeometry
from django.utils.text import slugify
from ..import_from_csv import ImportFromCSVCommand
from ...models import Locality


class Command(ImportFromCSVCommand):
    """
    Imports localities from the NPTG
    """
    def handle_rows(self, rows):
        existing_localities = Locality.objects.in_bulk()
        slugs = {
            locality.slug: locality for locality in existing_localities.values()
        }
        to_update = []
        to_create = []

        for row in rows:
            locality_code = row['NptgLocalityCode']
            if locality_code in existing_localities:
                locality = existing_localities[locality_code]
            else:
                locality = Locality()

            modified_at = row['ModificationDateTime']
            if modified_at:
                modified_at = parse_datetime(modified_at)
                if not modified_at.tzinfo:
                    modified_at = make_aware(modified_at)

            created_at = parse_datetime(row["CreationDateTime"])
            if not created_at.tzinfo:
                created_at = make_aware(created_at)

            if locality.id and modified_at == locality.modified_at:
                continue

            locality.modified_at = modified_at
            locality.created_at = created_at

            locality.name = row['LocalityName'].replace('\'', '\u2019')
            locality.short_name = row['ShortName']
            if locality.name == locality.short_name:
                locality.short_name = ''
            locality.qualifier_name = row['QualifierName']
            locality.admin_area_id = row['AdministrativeAreaCode']
            locality.latlong = GEOSGeometry(f"SRID=27700;POINT({row['Easting']} {row['Northing']})")

            if row['NptgDistrictCode'] == '310':  # bogus code seemingly used for localities with no district
                locality.district_id = None
            else:
                locality.district_id = row['NptgDistrictCode']

            if locality.id:
                to_update.append(locality)
            else:
                locality.id = locality_code

                slug = slugify(locality.get_qualified_name())
                locality.slug = slug
                i = 0
                while locality.slug in slugs:
                    i += 1
                    locality.slug = f"{slug}-{i}"

                slugs[locality.slug] = locality

                to_create.append(locality)

        Locality.objects.bulk_update(to_update, fields=[
            'name', 'qualifier_name', 'short_name', 'admin_area', 'latlong', 'modified_at', 'created_at', 'district'
        ], batch_size=100)
        Locality.objects.bulk_create(to_create)

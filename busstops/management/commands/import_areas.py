"""
Import administrative areas from the NPTG.

Usage:

    import_areas < AdminAreas.csv
"""

from ..import_from_csv import ImportFromCSVCommand
from ...models import AdminArea


class Command(ImportFromCSVCommand):

    def handle_row(self, row):
        AdminArea.objects.update_or_create(
            id=row['AdministrativeAreaCode'],
            defaults={
                'atco_code': row['AtcoAreaCode'],
                'name': row['AreaName'],
                'short_name': row['ShortName'],
                'country': row['Country'],
                'region_id': row['RegionCode'],
            }
        )

    def handle(self, *args, **options):
        super(Command, self).handle(*args, **options)

        # Move Cumbria to the North West.
        # Necessary because of the confusing 'North East and Cumbria' Traveline
        # region, but Cumbrian bus *services* are actually in the North West now
        AdminArea.objects.filter(name='Cumbria').update(region_id='NW')

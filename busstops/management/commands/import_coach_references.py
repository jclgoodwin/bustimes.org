"""Usage:

    ./manage.py import_coach_references < CoachReferences.csv
"""

# from django.contrib.gis.geos import Point
# from titlecase import titlecase
from ..import_from_csv import ImportFromCSVCommand
from ...models import DataSource, StopPoint, StopCode


class Command(ImportFromCSVCommand):
    input = 0
    encoding = 'windows-1252'

    def handle_row(self, row):
        source, _ = DataSource.objects.get_or_create(name='National coach code')
        stop = StopPoint.objects.get(atco_code=row['AtcoCode'])
        StopCode.objects.update_or_create(stop=stop, source=source, code=row['NationalCoachCode'])

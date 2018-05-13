"""
Usage:

    $ ./manage.py import_stops_in_area < StopsInArea.csv
"""
from warnings import warn
from ..import_from_csv import ImportFromCSVCommand
from ...models import StopArea, StopPoint


class Command(ImportFromCSVCommand):

    def handle_row(self, row):
        if StopArea.objects.filter(id=row['StopAreaCode']).exists():
            StopPoint.objects.filter(atco_code=row['AtcoCode']).update(
                stop_area_id=row['StopAreaCode']
            )
        else:
            warn(str(row))

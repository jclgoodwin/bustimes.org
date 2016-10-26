"""
Usage:

    $ ./manage.py import_stops_in_area < StopsInArea.csv
"""
import logging
from ..import_from_csv import ImportFromCSVCommand
from ...models import StopArea, StopPoint


logger = logging.getLogger(__name__)


class Command(ImportFromCSVCommand):

    def handle_row(self, row):
        if StopArea.objects.filter(id=row['StopAreaCode']).exists():
            StopPoint.objects.filter(atco_code=row['AtcoCode']).update(
                stop_area_id=row['StopAreaCode']
            )
        else:
            logger.error(row)

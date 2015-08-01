"""
Usage:

    $ ./manage.py import_stops_in_area < StopsInArea.csv
"""

from busstops.management.import_from_csv import ImportFromCSVCommand
from busstops.models import StopPoint, StopArea


class Command(ImportFromCSVCommand):

    def handle_row(self, row):
        area_id = row['StopAreaCode']
        stop = StopPoint.objects.get(atco_code=row['AtcoCode'])
        if stop.stop_area_id != area_id:
            area = StopArea.objects.get(id=area_id)
            stop.stop_area = area
            stop.save()

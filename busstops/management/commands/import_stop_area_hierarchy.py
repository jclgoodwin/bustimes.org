"""
Usage:

    $ ./manage.py import_stop_area_hierarchy < AreaHierarchy.py
"""

from ..import_from_csv import ImportFromCSVCommand
from ...models import StopArea


class Command(ImportFromCSVCommand):

    def handle_row(self, row):
        StopArea.objects.filter(id=row['ChildStopAreaCode']).update(
            parent_id=row['ParentStopAreaCode']
        )

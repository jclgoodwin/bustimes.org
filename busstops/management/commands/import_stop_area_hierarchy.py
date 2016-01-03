"""
Usage:

    $ ./manage.py import_stop_area_hierarchy < AreaHierarchy.py
"""

from busstops.management.import_from_csv import ImportFromCSVCommand
from busstops.models import StopArea


class Command(ImportFromCSVCommand):

    def handle_row(self, row):
        child = StopArea.objects.get(id=row['ChildStopAreaCode'])
        parent_id = row['ParentStopAreaCode']
        if child.parent_id != parent_id:
            child.parent_id = parent_id
            child.save()

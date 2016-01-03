"""
Add hierarchies to localities imported from the NPTG.

Usage:

    import_locality_hierarchy < LocalityHierarchy.csv
"""

from busstops.management.import_from_csv import ImportFromCSVCommand
from busstops.models import Locality


class Command(ImportFromCSVCommand):

    def handle_row(self, row):
        child = Locality.objects.get(id=row['ChildNptgLocalityCode'])
        parent_id = row['ParentNptgLocalityCode']
        if child.parent_id != parent_id:
            child.parent_id = parent_id
            child.save()

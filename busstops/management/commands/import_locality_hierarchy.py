"""
Usage:

    import_locality_hierarchy < LocalityHierarchy.csv
"""

from ..import_from_csv import ImportFromCSVCommand
from ...models import Locality


class Command(ImportFromCSVCommand):
    """
    Sets parent localities
    """
    def handle_row(self, row):
        child = Locality.objects.get(id=row['ChildNptgLocalityCode'])
        parent_id = row['ParentNptgLocalityCode']
        if child.parent_id != parent_id:
            child.parent_id = parent_id
            child.save()

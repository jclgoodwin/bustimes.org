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

    def handle_rows(self, rows):
        localities = Locality.objects.defer("search_vector", "latlong").in_bulk()
        to_update = []

        for row in rows:
            child = row["ChildNptgLocalityCode"]
            parent = row["ParentNptgLocalityCode"]

            if parent in localities and child in localities:
                child = localities[child]
                if child.parent_id != parent:
                    child.parent_id = parent
                    to_update.append(child)

        Locality.objects.bulk_update(to_update, ["parent"])

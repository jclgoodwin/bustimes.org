"""
Usage:

    import_adjacent_localities < AdjacentLocality.csv
"""

from ..import_from_csv import ImportFromCSVCommand
from ...models import Locality


class Command(ImportFromCSVCommand):
    def handle_row(self, row):
        locality = Locality.objects.get(id=row['NptgLocalityCode'])
        locality.adjacent.add(row['AdjacentNptgLocalityCode'])

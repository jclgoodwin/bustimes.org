"""
Import districts from the NPTG.

Usage:

    ./manage.py import_districts < Districts.csv
"""

from ..utils import parse_nptg_datetime
from .import_from_csv import ImportFromCSVCommand


class ImportNPTGCommand(ImportFromCSVCommand):
    def handle_rows(self, rows):
        existing = self.model.objects.in_bulk()

        to_create = []
        to_update = []

        for row in rows:
            modified_at = parse_nptg_datetime(row["ModificationDateTime"])

            pk = self.get_pk(row)
            if pk in existing and existing[pk].modified_at == modified_at:
                continue

            new = self.handle_row(row)
            new.pk = pk
            new.modified_at = modified_at
            new.created_at = parse_nptg_datetime(row["CreationDateTime"])

            if pk in existing:
                to_update.append(new)
            else:
                to_create.append(new)

        self.model.objects.bulk_update(
            to_update,
            fields=self.update_fields + ["modified_at", "created_at"],
            batch_size=100,
        )
        self.model.objects.bulk_create(to_create)

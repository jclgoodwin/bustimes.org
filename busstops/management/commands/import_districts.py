"""
Import districts from the NPTG.

Usage:

    ./manage.py import_districts < Districts.csv
"""

from ..import_nptg import ImportNPTGCommand
from ...models import District


class Command(ImportNPTGCommand):
    model = District
    update_fields = ["name", "admin_area_id"]

    def get_pk(self, row):
        return int(row["DistrictCode"])

    def handle_row(self, row):
        return District(
            name=row["DistrictName"].replace("'", "\u2019"),
            admin_area_id=row["AdministrativeAreaCode"],
        )

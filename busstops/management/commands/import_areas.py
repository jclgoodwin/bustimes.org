"""
Import administrative areas from the NPTG.

Usage:

    ./manage.py import_areas < AdminAreas.csv
"""

from ..import_nptg import ImportNPTGCommand
from ...models import AdminArea


class Command(ImportNPTGCommand):
    model = AdminArea
    update_fields = ["atco_code", "name", "short_name", "country", "region"]

    def get_pk(self, row):
        return int(row["AdministrativeAreaCode"])

    def handle_row(self, row):
        area = AdminArea(
            atco_code=row["AtcoAreaCode"],
            name=row["AreaName"],
            short_name=row["ShortName"],
            country=row["Country"],
            region_id=row["RegionCode"],
        )

        # Move Cumbria to the North West instead of the 'North East and Cumbria' Traveline region
        # (Cumbrian bus *services* are in the North West region now)
        if area.name == "Cumbria":
            area.region_id = "NW"

        return area

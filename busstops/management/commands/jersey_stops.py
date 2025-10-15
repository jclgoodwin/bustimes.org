import json
from pathlib import Path

from django.contrib.gis.geos import GEOSGeometry
from django.core.management.base import BaseCommand
from ...models import DataSource, StopPoint


class Command(BaseCommand):
    def handle(self, *args, **options):
        source, _ = DataSource.objects.get_or_create(name="Jersey")

        with (
            Path(__file__).resolve().parent.parent.parent / "jersey-bus-stops.json"
        ).open() as fp:
            stops = json.load(fp)["stops"]

        stops = [
            StopPoint(
                source=source,
                atco_code=f"{source.id}:{stop['StopNumber']}",
                common_name=stop["StopName"],
                latlong=GEOSGeometry(f"POINT({stop['Longitude']} {stop['Latitude']})"),
                active=True,
            )
            for stop in stops
        ]

        StopPoint.objects.bulk_create(stops, ignore_conflicts=True)

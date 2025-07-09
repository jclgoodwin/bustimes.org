import logging
from django.core.management.base import BaseCommand
from pyrosm import get_data, OSM

from busstops.models import DataSource, StopPoint

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    def handle(self, *args, **options):
        source, name = DataSource.objects.get_or_create(name="OpenStreetMap")
        self.source = source

        existing_stops = StopPoint.objects.filter(
            atco_code__startswith="8910850"
        ).in_bulk()

        fp = get_data("isle-of-man")

        osm = OSM(fp)
        # Get all bus stops
        bus_stops = osm.get_data_by_custom_criteria(
            custom_filter={
                "highway": ["bus_stop"],
            }
        )
        to_update = {}
        to_create = {}
        for bs in bus_stops.itertuples():
            if bs.ref and bs.name and len(bs.ref) <= 6:
                atco_code = f"891085{bs.ref.zfill(6)}"
                if bs.geometry.geom_type != "Point":
                    latlong = bs.geometry.centroid.wkt
                else:
                    latlong = bs.geometry.wkt
                if stop := existing_stops.get(atco_code):
                    if bs.name:
                        stop.common_name = bs.name
                    stop.source = self.source
                    stop.latlong = latlong
                    if atco_code in to_update:
                        logger.warning(
                            f"Duplicate ATCO code found: {atco_code} for {bs.name}"
                        )
                    to_update[atco_code] = stop
                else:
                    if atco_code in to_create:
                        logger.warning(
                            f"Duplicate ATCO code found: {atco_code} for {bs.name}"
                        )
                    to_create[atco_code] = StopPoint(
                        atco_code=atco_code,
                        common_name=bs.name,
                        source=self.source,
                        latlong=latlong,
                        active=True,
                    )

        StopPoint.objects.bulk_update(
            to_update.values(), ["common_name", "latlong", "source"]
        )
        StopPoint.objects.bulk_create(to_create.values())

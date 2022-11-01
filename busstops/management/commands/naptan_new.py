import logging
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
import yaml
from ciso8601 import parse_datetime
from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry
from django.core.management.base import BaseCommand
from django.utils.timezone import make_aware

from busstops.models import AdminArea, DataSource, StopArea, StopPoint

logger = logging.getLogger(__name__)


def get_datetime(string):
    datetime = parse_datetime(string)
    if not datetime.tzinfo:
        return make_aware(datetime)
    return datetime


class Command(BaseCommand):
    mapping = (
        ("Descriptor/CommonName", "common_name"),
        ("Descriptor/Landmark", "landmark"),
        ("Descriptor/Street", "street"),
        ("Descriptor/Indicator", "indicator"),
        ("Descriptor/Crossing", "crossing"),
        ("Place/Suburb", "suburb"),
        ("Place/Town", "town"),
        ("StopClassification/StopType", "stop_type"),
        ("StopClassification/OnStreet/Bus/BusStopType", "bus_stop_type"),
        ("StopClassification/OnStreet/Bus/TimingStatus", "timing_status"),
    )

    # dumb placeholders in the data that should be blank
    nothings = {
        "-",
        "--",
        "---",
        "Crossing not known",
        "Street not known",
        "Landmark not known",
        "Unknown",
        "*",
        "Data Unavailable",
        "N/A",
        "Tba",
        "type_undefined",
        "class_undefined",
    }

    def get_stop(self, element):
        atco_code = element.findtext("AtcoCode")

        modified_at = element.attrib.get("ModificationDateTime")
        if modified_at:
            modified_at = get_datetime(modified_at)

        if (
            atco_code in self.existing_stops
            and modified_at == self.existing_stops[atco_code].modified_at
            and atco_code not in self.overrides
        ):
            return

        created_at = get_datetime(element.attrib["CreationDateTime"])

        easting = element.findtext("Place/Location/Easting")
        northing = element.findtext("Place/Location/Northing")
        grid_type = element.findtext("Place/Location/GridType")

        if not easting:
            easting = element.findtext("Place/Location/Translation/Easting")
            northing = element.findtext("Place/Location/Translation/Northing")
            grid_type = element.findtext("Place/Location/Translation/GridType")
        if easting:
            match grid_type:
                case "ITM":
                    srid = 2157
                case "IrishOS":
                    assert (
                        atco_code[0] != "8"
                    )  # not actually in Ireland, must be a mistake
                    srid = 27700
                case "UKOS" | None:
                    srid = 27700
            point = GEOSGeometry(f"SRID={srid};POINT({easting} {northing})")
        else:
            lon = element.findtext("Place/Location/Translation/Longitude")
            lat = element.findtext("Place/Location/Translation/Latitude")
            if lat is not None and lon is not None:
                point = GEOSGeometry(f"POINT({lon} {lat})")
            else:
                point = None

        bearing = element.findtext(
            "StopClassification/OnStreet/Bus/MarkedPoint/Bearing/CompassPoint"
        )
        if bearing is None:
            bearing = element.findtext(
                "StopClassification/OnStreet/Bus/UnmarkedPoint/Bearing/CompassPoint"
            )
        if bearing is None:
            bearing = ""

        stop = StopPoint(
            atco_code=atco_code,
            naptan_code=element.findtext("NaptanCode") or element.findtext("PlateCode"),
            created_at=created_at,
            modified_at=modified_at,
            latlong=point,
            bearing=bearing,
            locality_id=element.findtext("Place/NptgLocalityRef"),
            admin_area_id=element.findtext("AdministrativeAreaRef"),
            stop_area_id=element.findtext("StopAreas/StopAreaRef"),
            active="Status" not in element.attrib
            or element.attrib["Status"] == "active",
        )
        if atco_code.startswith(stop.admin_area_id):
            stop.admin_area = self.admin_areas.get(stop.admin_area_id)
            logger.info(f"{atco_code} {stop.admin_area}")

        for xml_path, key in self.mapping:
            value = element.findtext(xml_path, "")
            if value in self.nothings:
                value = ""
            setattr(stop, key, value)

        if stop.indicator == stop.naptan_code:
            stop.indicator = ""

        if atco_code in self.overrides:
            for key, value in self.overrides[atco_code].items():
                if key == "latlong":
                    value = GEOSGeometry(value)
                setattr(stop, key, value)

        if atco_code in self.existing_stops:
            self.stops_to_update.append(stop)
        else:
            self.stops_to_create.append(stop)

    bulk_update_fields = [
        "created_at",
        "modified_at",
        "naptan_code",
        "latlong",
        "bearing",
        "common_name",
        "landmark",
        "street",
        "crossing",
        "stop_type",
        "bus_stop_type",
        "timing_status",
        "locality",
        "admin_area",
        "stop_area",
        "indicator",
        "suburb",
        "town",
        "active",
    ]

    def download(self, source):
        url = "https://naptan.api.dft.gov.uk/v1/access-nodes"
        params = {"dataFormat": "xml"}

        return requests.get(url, params, timeout=60, stream=True)

    def update_and_create(self):
        # create any new stop areas
        stops = [stop for stop in self.stops_to_create if stop.stop_area_id]
        stops += [stop for stop in self.stops_to_update if stop.stop_area_id]

        stop_areas = StopArea.objects.in_bulk([stop.stop_area_id for stop in stops])
        stop_areas_to_create = set(
            StopArea(
                id=stop.stop_area_id, active=True, admin_area_id=stop.admin_area_id
            )
            for stop in stops
            if stop.stop_area_id not in stop_areas
        )
        StopArea.objects.bulk_create(stop_areas_to_create, batch_size=100)

        # create new stops
        StopPoint.objects.bulk_create(self.stops_to_create, batch_size=100)
        self.stops_to_create = []

        # update updated stops
        StopPoint.objects.bulk_update(
            self.stops_to_update, self.bulk_update_fields, batch_size=100
        )
        self.stops_to_update = []

    @staticmethod
    def add_arguments(parser):
        parser.add_argument("filename", nargs="?", type=str)

    def handle(self, *args, **options):
        source, created = DataSource.objects.get_or_create(name="NaPTAN")

        if options["filename"]:
            path = Path(options["filename"])
        else:
            path = settings.DATA_DIR / "naptan.xml"

            # download new data if there is any
            response = self.download(source)
            if response:
                with path.open("wb") as open_file:
                    for chunk in response.iter_content(chunk_size=102400):
                        open_file.write(chunk)

        # set up overrides/corrections
        overrides_path = settings.BASE_DIR / "fixtures" / "stops.yaml"
        with overrides_path.open() as open_file:
            self.overrides = yaml.load(open_file, yaml.BaseLoader)

        self.stops_to_create = []
        self.stops_to_update = []
        self.admin_areas = {
            admin_area.atco_code: admin_area for admin_area in AdminArea.objects.all()
        }
        atco_code_prefix = None

        iterator = ET.iterparse(path, events=["start", "end"])
        for event, element in iterator:
            if event == "start":
                if element.tag == "{http://www.naptan.org.uk/}NaPTAN":
                    modified_at = get_datetime(element.attrib["ModificationDateTime"])
                    if modified_at == source.datetime:
                        return

                    source.datetime = modified_at

                continue

            element.tag = element.tag.removeprefix("{http://www.naptan.org.uk/}")
            if element.tag == "StopPoint":
                atco_code = element.findtext("AtcoCode")
                if atco_code[:3] != atco_code_prefix:

                    if atco_code_prefix:
                        self.update_and_create()

                    atco_code_prefix = atco_code[:3]

                    self.existing_stops = (
                        StopPoint.objects.only("atco_code", "modified_at")
                        .filter(atco_code__startswith=atco_code_prefix)
                        .in_bulk()
                    )

                self.get_stop(element)

                element.clear()  # save memory

        self.update_and_create()

        if not options["filename"]:
            source.save(update_fields=["datetime"])

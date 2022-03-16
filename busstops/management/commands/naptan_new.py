import yaml
import requests
import xml.etree.ElementTree as ET
from django.contrib.gis.geos import GEOSGeometry
from ciso8601 import parse_datetime
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.timezone import make_aware
from busstops.models import StopArea, DataSource, StopPoint, AdminArea


class Command(BaseCommand):
    mapping = (
        ("Descriptor/CommonName", "common_name"),
        ("Descriptor/Landmark", "landmark"),
        ("Descriptor/Street", "street"),
        ("Descriptor/Indicator", "indicator"),
        ("Descriptor/Crossing", "crossing"),
        ("Place/Suburb", "suburb"),
        ("Place/Town", "town"),
    )

    # dumb placeholders in the data that should be blank
    nothings = (
        "-",
        "---",
        "Crossing not known",
        "Street not known",
        "Landmark not known",
        "Unknown",
        "*",
        "Data Unavailable",
        "N/A",
        "Tba",
    )

    def get_stop(self, element):
        atco_code = element.findtext("AtcoCode")

        modified_at = element.attrib.get("ModificationDateTime")
        if modified_at:
            modified_at = parse_datetime(modified_at)
            if not modified_at.tzinfo:
                modified_at = make_aware(modified_at)

        if (
            atco_code in self.existing_stops
            and modified_at == self.existing_stops[atco_code].modified_at
            and atco_code not in self.overrides
        ):
            return

        created_at = parse_datetime(element.attrib["CreationDateTime"])
        if not created_at.tzinfo:
            created_at = make_aware(created_at)

        easting = element.findtext("Place/Location/Easting")
        northing = element.findtext("Place/Location/Northing")
        if not easting:
            easting = element.findtext("Place/Location/Translation/Easting")
            northing = element.findtext("Place/Location/Translation/Northing")
        if easting:
            point = GEOSGeometry(f"SRID=27700;POINT({easting} {northing})")
        else:
            lon = element.findtext("Place/Location/Translation/Longitude")
            lat = element.findtext("Place/Location/Translation/Latitude")
            point = GEOSGeometry(f"POINT({lon} {lat})")

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
            naptan_code=element.findtext("NaptanCode"),
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
            stop.admin_area = self.admin_areas[stop.admin_area_id]
            print(atco_code, stop.admin_area)

        for xml_path, key in self.mapping:
            value = element.findtext(xml_path, "")
            if value in self.nothings:
                value = ""
            setattr(stop, key, value)

        if stop.indicator == stop.naptan_code:
            stop.indicator = ""

        if atco_code in self.overrides:
            for key, value in self.overrides[atco_code].items():
                if key == 'latlong':
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
        "locality",
        "admin_area",
        "stop_area",
        "indicator",
        "suburb",
        "town",
        "active",
    ]

    def download(self, source):
        response = requests.get(
            "https://naptan.app.dft.gov.uk/GridMethods/NPTGLastSubs_Load.ashx",
            timeout=10,
        )
        new_rows = response.json()
        old_rows = source.settings

        url = "https://naptan.api.dft.gov.uk/v1/access-nodes"
        params = {"dataFormat": "xml"}

        if old_rows:
            changes = [
                new_row["DataBaseID"]
                for i, new_row in enumerate(new_rows)
                if old_rows[i]["LastUpload"] != new_row["LastUpload"]
            ]

            if not changes:
                return

            params["atcoAreaCodes"] = ",".join(changes)

        source.settings = new_rows

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

    def handle(self, *args, **options):
        source, created = DataSource.objects.get_or_create(name="NaPTAN")

        path = settings.DATA_DIR / "naptan.xml"

        # download new data if there is any
        response = self.download(source)
        if response:
            with path.open("wb") as open_file:
                for chunk in response.iter_content(chunk_size=102400):
                    open_file.write(chunk)

        source.save(update_fields=["settings"])

        # set up overrides/corrections
        overrides_path = settings.DATA_DIR / "stops.yaml"
        with overrides_path.open() as open_file:
            self.overrides = yaml.load(open_file, yaml.BaseLoader)

        self.stops_to_create = []
        self.stops_to_update = []
        self.admin_areas = {
            admin_area.atco_code: admin_area for admin_area in AdminArea.objects.all()
        }
        atco_code_prefix = None

        iterator = ET.iterparse(path)
        for _, element in iterator:

            element.tag = element.tag.removeprefix("{http://www.naptan.org.uk/}")
            if element.tag == "StopPoint":
                atco_code = element.findtext("AtcoCode")
                if atco_code[:3] != atco_code_prefix:

                    if atco_code_prefix:
                        self.update_and_create()

                    atco_code_prefix = atco_code[:3]
                    print(atco_code_prefix)

                    self.existing_stops = (
                        StopPoint.objects.only("atco_code", "modified_at")
                        .filter(atco_code__startswith=atco_code_prefix)
                        .in_bulk()
                    )

                self.get_stop(element)

                element.clear()  # save memory

        self.update_and_create()

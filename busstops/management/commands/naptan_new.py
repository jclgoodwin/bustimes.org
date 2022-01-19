import requests
import xml.etree.ElementTree as ET
from django.contrib.gis.geos import GEOSGeometry
from ciso8601 import parse_datetime
from django.utils.timezone import make_aware
from django.conf import settings
from django.core.management.base import BaseCommand
from busstops.models import DataSource, StopPoint


class Command(BaseCommand):
    def get_stop(self, element):
        atco_code = element.findtext("AtcoCode")

        modified_at = element.attrib.get("ModificationDateTime")
        if modified_at:
            modified_at = parse_datetime(modified_at)
            if not modified_at.tzinfo:
                modified_at = make_aware(modified_at)

        if atco_code in self.existing_stops and modified_at == self.existing_stops[atco_code].modified_at:
            return

        created_at = parse_datetime(element.attrib["CreationDateTime"])
        if not created_at.tzinfo:
            created_at = make_aware(created_at)

        # ET.indent(element)
        # print(ET.tostring(element).decode())

        lon = element.findtext("Place/Location/Translation/Longitude")
        if lon:
            lat = element.findtext("Place/Location/Translation/Latitude")
            point = GEOSGeometry(f"POINT({lon} {lat})")
        else:
            easting = element.findtext("Place/Location/Easting")
            northing = element.findtext("Place/Location/Northing")
            point = GEOSGeometry(f"SRID=27700;POINT({easting} {northing})")
        # print(point)

        bearing = element.findtext("StopClassification/OnStreet/Bus/MarkedPoint/Bearing/CompassPoint")
        if bearing is None:
            bearing = element.findtext("StopClassification/OnStreet/Bus/UnmarkedPoint/Bearing/CompassPoint")
        if bearing is None:
            bearing = ""

        stop = StopPoint(
            atco_code=atco_code,
            naptan_code=element.findtext("NaptanCode", ""),

            created_at=created_at,
            modified_at=modified_at,

            latlong=point,

            bearing=bearing,

            common_name=element.findtext("Descriptor/CommonName", ""),
            landmark=element.findtext("Descriptor/Landmark", ""),
            street=element.findtext("Descriptor/Street", ""),
            indicator=element.findtext("Descriptor/Indicator", ""),

            locality_id=element.findtext("Place/NptgLocalityRef"),
            suburb=element.findtext("Place/Suburb", ""),
            town=element.findtext("Place/Town", ""),

            active=element.attrib["Status"] == "active"
        )

        if atco_code in self.existing_stops:
            self.stops_to_update.append(stop)
        else:
            self.stops_to_create.append(stop)

    bulk_update_fields = [
        'created_at',
        'modified_at',
        'naptan_code',
        'latlong',
        'bearing',
        'common_name',
        'landmark',
        'street',
        'locality',
        'indicator',
        'suburb',
        'town',
        'active',
    ]

    def download(self, source):
        response = requests.get("https://naptan.app.dft.gov.uk/GridMethods/NPTGLastSubs_Load.ashx", timeout=10)
        new_rows = response.json()
        old_rows = source.settings

        url = "https://naptan.api.dft.gov.uk/v1/access-nodes"
        params = {
            "dataFormat": "xml"
        }

        if old_rows:
            changes = [new_row['DataBaseID'] for i, new_row in enumerate(new_rows)
                       if old_rows[i]['LastUpload'] != new_row['LastUpload']]

            if not changes:
                return

            params["atcoAreaCodes"] = ",".join(changes)

        source.settings = new_rows

        return requests.get(url, params, timeout=10, stream=True)

    def handle(self, *args, **options):
        source, created = DataSource.objects.get_or_create(name='NaPTAN')

        path = settings.DATA_DIR / "naptan.xml"

        response = self.download(source)
        if response:
            with path.open("wb") as open_file:
                for chunk in response.iter_content(chunk_size=102400):
                    open_file.write(chunk)

        self.stops_to_create = []
        self.stops_to_update = []
        atco_code_prefix = None

        iterator = ET.iterparse(path)
        for _, element in iterator:

            element.tag = element.tag.removeprefix("{http://www.naptan.org.uk/}")
            if element.tag == "StopPoint":
                atco_code = element.findtext("AtcoCode")
                if atco_code[:3] != atco_code_prefix:

                    if atco_code_prefix:
                        StopPoint.objects.bulk_create(self.stops_to_create)
                        StopPoint.objects.bulk_update(self.stops_to_update, self.bulk_update_fields)
                        self.stops_to_create = []
                        self.stops_to_update = []

                    atco_code_prefix = atco_code[:3]

                    self.existing_stops = StopPoint.objects.only(
                        'atco_code', 'modified_at'
                    ).filter(
                        atco_code__startswith=atco_code_prefix
                    ).in_bulk()

                self.get_stop(element)

                element.clear()  # save memory

        StopPoint.objects.bulk_create(self.stops_to_create)
        StopPoint.objects.bulk_update(self.stops_to_update, self.bulk_update_fields)

        source.save(update_fields=["settings"])

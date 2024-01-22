import io
import xml.etree.cElementTree as ET
import zipfile

import requests
from django.core.management.base import BaseCommand

from busstops.models import DataSource

from .import_siri_sx import handle_item


class Command(BaseCommand):
    def fetch(self):
        url = "https://data.bus-data.dft.gov.uk/disruptions/download/bulk_archive"

        source = DataSource.objects.get_or_create(name="Bus Open Data")[0]

        situations = []

        response = requests.get(url, timeout=10)
        assert response.ok

        archive = zipfile.ZipFile(io.BytesIO(response.content))

        namelist = archive.namelist()
        assert len(namelist) == 1
        open_file = archive.open(namelist[0])

        for _, element in ET.iterparse(open_file):
            if element.tag[:29] == "{http://www.siri.org.uk/siri}":
                element.tag = element.tag[29:]

            if element.tag.endswith("PtSituationElement"):
                situations.append(handle_item(element, source))
                element.clear()

        source.situation_set.filter(current=True).exclude(id__in=situations).update(
            current=False
        )

    def handle(self, *args, **options):
        self.fetch()

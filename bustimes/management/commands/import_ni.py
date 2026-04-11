import pprint
from datetime import datetime, timezone
from pathlib import Path

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from busstops.models import DataSource

from ...download_utils import download
from .import_atco_cif import Command as ImportAtcoCif


class Command(BaseCommand):
    """
    Check the Open Data NI (Northern Ireland) website CKAN API for any new
    Translink Metro and Ulsterbus data,
    and download it and call the import_atco_cif command if necessary
    """

    def handle(self, *args, **options):
        base_url = "https://admin.opendatani.gov.uk/api/3/action/package_show"
        ids = [
            "ulsterbus-and-goldline-timetable-data-from-08-11-2023",
            "metro-timetable-data-valid-from-18-june-until-31-august-2016",
        ]

        for _id in ids:
            response = requests.get(base_url, params={"id": _id})
            data = response.json()

            source = DataSource.objects.get(url__endswith=_id)

            for resource in data["result"]["resources"]:
                dt = resource["last_modified"] or resource["created"]
                dt = datetime.fromisoformat(dt).replace(tzinfo=timezone.utc)

                if source.datetime is None or dt > source.datetime:
                    # new data, lorks a lordy!

                    pprint.pprint(resource)

                    url = resource["url"]
                    path = Path(settings.DATA_DIR) / f"{source.id}.zip"
                    download(path, url)

                    command = ImportAtcoCif()
                    command.source = source
                    command.source.datetime = dt

                    command.handle_archive(path)

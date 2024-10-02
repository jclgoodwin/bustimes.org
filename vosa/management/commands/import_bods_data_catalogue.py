import csv
import io
import logging
import zipfile
from datetime import datetime

from django.conf import settings
from django.core.management import BaseCommand

from bustimes.download_utils import download_if_modified

from ...models import Licence, Registration  # , Variation

logger = logging.getLogger(__name__)


def parse_date(date_string: str):
    if date_string:
        return datetime.strptime(date_string, "%d/%m/%y").date()


class Command(BaseCommand):
    def get_rows(self, path: str):
        with open(settings.DATA_DIR / path) as open_file:
            yield from csv.DictReader(open_file)

    def handle(self, **kwargs) -> None:
        is_modified, modified_at = download_if_modified(
            settings.DATA_DIR / "data_catalogue.zip",
            url="https://data.bus-data.dft.gov.uk/catalogue/",
        )
        print(is_modified, modified_at)

        lics = Licence.objects.in_bulk(field_name="licence_number")
        lics_to_create = []
        # lics_to_update = []

        regs = Registration.objects.in_bulk(field_name="registration_number")
        regs_to_create = []
        regs_to_update = []

        with (
            zipfile.ZipFile(settings.DATA_DIR / "data_catalogue.zip") as z,
            z.open("timetables_data_catalogue.csv", mode="r") as f,
            io.TextIOWrapper(f) as wrapped_f,
        ):
            for row in csv.DictReader(wrapped_f):
                if row["OTC:Registration Number"]:
                    reg = regs.get(row["OTC:Registration Number"])
                    if not reg:
                        lic = lics.get(row["OTC:Licence Number"])
                        assert row["OTC Status"] == "Registered"

                        if not lic:
                            continue

                        reg = Registration(
                            registration_number=row["OTC:Registration Number"],
                            registered=True,
                            licence=lic,
                        )
                    reg.service_number = row["OTC:Service Number"]
                    reg.start_point = row["OTC:Start Point"]
                    reg.finish_point = row["OTC:Finish Point"]
                    reg.via = row["OTC:Via"]
                    reg.service_type_description = row["OTC:Service Type Description"]

                    if reg.id:
                        regs_to_update.append(reg)
                    else:
                        regs_to_create.append(reg)

        Licence.objects.bulk_create(lics_to_create)
        Registration.objects.bulk_create(regs_to_create)
        Registration.objects.bulk_update(
            regs_to_update,
            [
                "service_number",
                "start_point",
                "finish_point",
                "via",
                "service_type_description",
            ],
        )

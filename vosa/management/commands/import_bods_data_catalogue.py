import csv
import io
import logging
import zipfile

from django.conf import settings
from django.core.management import BaseCommand

from bustimes.download_utils import download_if_modified

from busstops.models import DataSource
from ...models import Licence, Registration, Variation

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    def get_rows(self, path: str):
        with open(settings.DATA_DIR / path) as open_file:
            yield from csv.DictReader(open_file)

    def handle(self, **kwargs) -> None:
        source, _ = DataSource.objects.get_or_create(
            url="https://data.bus-data.dft.gov.uk/catalogue/"
        )
        is_modified, modified_at = download_if_modified(
            settings.DATA_DIR / "data_catalogue.zip", source
        )
        print(is_modified, modified_at)

        lics = Licence.objects.in_bulk(field_name="licence_number")
        lics_to_create = []
        # lics_to_update = []

        regs = Registration.objects.in_bulk(field_name="registration_number")
        regs_to_create = []
        regs_to_update = []

        variations = []

        with (
            zipfile.ZipFile(settings.DATA_DIR / "data_catalogue.zip") as z,
            z.open("timetables_data_catalogue.csv", mode="r") as f,
            io.TextIOWrapper(f) as wrapped_f,
        ):
            for row in csv.DictReader(wrapped_f):
                if reg_no := row["OTC:Registration Number"]:
                    reg = regs.get(reg_no)
                    if not reg:
                        lic = lics.get(row["OTC:Licence Number"])
                        assert row["OTC Status"] == "Registered"

                        if not lic:
                            continue

                        reg = Registration(
                            registration_number=reg_no,
                            registered=True,
                            licence=lic,
                        )
                    reg.service_number = row["OTC:Service Number"]
                    reg.start_point = row["OTC:Start Point"]
                    reg.finish_point = row["OTC:Finish Point"]
                    reg.via = row["OTC:Via"]
                    reg.service_type_description = row[
                        "OTC:Service Type Description"
                    ].removesuffix("�")
                    reg.traffic_area_office_covered_by_area = row[
                        "Traveline Region"
                    ].replace("|", "\n")
                    reg.authority_description = row[
                        "Local Transport Authority"
                    ].replace("|", "\n")

                    if reg.id:
                        regs_to_update.append(reg)
                    elif reg_no not in regs:
                        regs_to_create.append(reg)

                        regs[reg_no] = reg

                    variation = Variation(
                        registration=reg,
                        variation_number=row["OTC:Variation Number"],
                        effective_date=row["OTC:Effective Date"] or None,
                        date_received=row["OTC:Received Date"] or None,
                        service_type_other_details=row[
                            "OTC:Service Type Other Details"
                        ],
                    )
                    variations.append(variation)

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
                "traffic_area_office_covered_by_area",
                "authority_description",
            ],
        )

        Variation.objects.bulk_create(
            variations,
            ignore_conflicts=True,
        )

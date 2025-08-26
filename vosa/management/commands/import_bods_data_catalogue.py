import csv
import io
import logging
import zipfile

from django.conf import settings
from django.core.management import BaseCommand

from bustimes.download_utils import download_if_modified

from busstops.models import DataSource
from ...models import Licence, Registration, Variation
from ciso8601 import parse_datetime

logger = logging.getLogger(__name__)


# mapping of database model field names to spreadsheet column names
var_mapping = (
    ("effective_date", "OTC:Effective Date"),
    ("date_received", "OTC:Received Date"),
    ("service_type_other_details", "OTC:Service Type Other Details"),
)
reg_mapping = (
    ("service_number", "OTC:Service Number"),
    ("start_point", "OTC:Start Point"),
    ("finish_point", "OTC:Finish Point"),
    ("via", "OTC:Via"),
    ("service_type_description", "OTC:Service Type Description"),
    ("traffic_area_office_covered_by_area", "Traveline Region"),
    ("authority_description", "Local Transport Authority"),
)


class Command(BaseCommand):
    """Use the BODS "data catalogue" to supplement the Traffic Commissioners' data.
    Because the data catalogue includes devolved registrations, and is sometimes a bit more up-to-date, etc.
    """

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

        regs = Registration.objects.in_bulk(field_name="registration_number")
        regs_to_create = []
        regs_to_update = []

        variations = {
            f"{v.registration_id}:{v.variation_number}": v
            for v in Variation.objects.all()
        }
        vars_to_create = []
        vars_to_update = []

        previous_reg_no = None

        with (
            zipfile.ZipFile(settings.DATA_DIR / "data_catalogue.zip") as z,
            z.open("timetables_data_catalogue.csv", mode="r") as f,
            io.TextIOWrapper(f) as wrapped_f,
        ):
            for row in csv.DictReader(wrapped_f):
                reg_no = row["OTC:Registration Number"]
                if not reg_no or reg_no == previous_reg_no:
                    continue

                previous_reg_no = reg_no

                # Registration

                reg = regs.get(reg_no)
                if not reg:
                    lic = lics.get(row["OTC:Licence Number"])
                    assert row["OTC Status"] == "Registered"

                    if not lic:
                        print(f"unknown licence {row}")
                        continue

                    reg = Registration(
                        registration_number=reg_no,
                        registered=True,
                        licence=lic,
                    )
                    changed = True
                else:
                    changed = not reg.registered

                for a, b in reg_mapping:
                    to_value = row[b]
                    if a != "service_number":
                        to_value = to_value.replace("|", "\n").removesuffix("�").strip()

                    if getattr(reg, a) != to_value:
                        setattr(reg, a, to_value)
                        changed = True

                if changed:
                    if reg.id:
                        regs_to_update.append(reg)
                    elif reg_no not in regs:
                        regs_to_create.append(reg)

                        regs[reg_no] = reg

                # Variation

                variation_number = row["OTC:Variation Number"]
                variation = None
                if reg.id:
                    variation = variations.get(f"{reg.id}:{variation_number}")
                if not variation:
                    variation = Variation(
                        registration=reg, variation_number=variation_number
                    )
                changed = False
                for a, b in var_mapping:
                    to_value = row[b]
                    if "date" in a:
                        if to_value:
                            to_value = parse_datetime(to_value).date()
                        else:
                            to_value = None  # use None instead of the empty string ""
                    if getattr(variation, a) != to_value:
                        setattr(variation, a, to_value)
                        changed = True
                if changed:
                    if variation.id:
                        vars_to_update.append(variation)
                    else:
                        vars_to_create.append(variation)

        print(f"{len(lics_to_create)=}")
        print(f"{len(regs_to_create)=}")
        print(f"{len(regs_to_update)=}")
        print(f"{len(vars_to_create)=}")
        print(f"{len(vars_to_update)=}")

        Licence.objects.bulk_create(lics_to_create)
        Registration.objects.bulk_create(regs_to_create)
        Registration.objects.bulk_update(regs_to_update, [a for a, _ in reg_mapping])

        Variation.objects.bulk_create(vars_to_create)
        Variation.objects.bulk_update(vars_to_update, [a for a, _ in var_mapping])

import csv

from django.conf import settings
from django.core.management import BaseCommand

from bustimes.download_utils import download_if_changed

from ...models import Operator


def get_region_id(region_id):
    if region_id in {"ADMIN", "Admin", "Taxi", ""}:
        return "GB"
    elif region_id.upper() in {"SC", "YO", "WA", "LO"}:
        return region_id[0]
    return region_id


def get_mode(mode):
    if not mode.isupper():
        mode = mode.lower()
    match mode:
        case "ct operator" | "ct operaor" | "CT":
            return "community transport"
        case "DRT":
            return "demand responsive transport"
        case "partly drt":
            return "partly DRT"
    return mode


def get_rows(path):
    with open(path) as open_file:
        for line in csv.DictReader(open_file):
            yield line


class Command(BaseCommand):
    def handle(self, **kwargs):
        url = "https://mytraveline.info/NOC/NOC_DB.csv"
        path = settings.DATA_DIR / "NOC_DB.csv"
        modified, last_modified = download_if_changed(path, url)

        print(modified, last_modified)

        operators = Operator.objects.prefetch_related(
            "operatorcode_set", "licences"
        ).in_bulk()

        to_update = []
        modes = set()

        for row in get_rows(path):
            noc = row["NOCCODE"]
            if noc[:1] == "=":
                noc = noc[1:]
            assert "=" not in noc

            mode = get_mode(row["Mode"])
            modes.add(mode)

            if noc in operators:
                operator = operators[noc]
                to_update.append(operator)
            else:
                operator = Operator(region_id=get_region_id(row["TLRegOwn"]))

            if noc == "AMSY":
                operator.name = row["RefNm"]
            else:
                operator.name = row["OperatorPublicName"]

            if not operator.noc:
                operator.noc = noc
                operator.save()

        Operator.objects.bulk_update(to_update, ["name"])

        print(modes)

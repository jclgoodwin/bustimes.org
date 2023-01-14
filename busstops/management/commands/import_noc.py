import csv
import io
import xml.etree.ElementTree as ET

import requests
import yaml
from django.conf import settings
from django.core.management import BaseCommand
from django.utils.text import slugify

from ...models import DataSource, Operator, OperatorCode


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


def noc_csv(code_sources: list, operators: dict):
    operator_codes = []
    names = {}

    url = "https://mytraveline.info/NOC/NOC_DB.csv"

    response = requests.get(url)

    for row in csv.DictReader(io.StringIO(response.text)):
        if row["Date Ceased"]:
            continue

        noc = row["NOCCODE"]
        if noc[:1] == "=":
            noc = noc[1:]
        assert "=" not in noc

        if noc == "#NAME?":  # microsoft excel crap
            continue
        assert len(noc) <= 4

        mode = get_mode(row["Mode"])

        if mode == "airline":
            continue

        if noc in operators:
            operator = operators[noc]
        else:
            operator = Operator(
                region_id=get_region_id(row["TLRegOwn"]), vehicle_mode=mode
            )
            operators[noc] = operator

        if noc == "AMSY":
            operator.name = row["RefNm"]
        else:
            operator.name = row["OperatorPublicName"]

        slug = operator.slug or slugify(operator.name)

        if not operator.noc:
            operator.noc = noc

            if slug in names:  # cope with duplicate slug
                if not names[slug].slug:
                    names[slug].save(force_insert=True)
                    operator.save(force_insert=True)

            operator_codes.append(
                OperatorCode(source=code_sources[0][1], code=noc, operator=operator)
            )

            for col, source in code_sources[1:]:
                if row[col] and row[col] != noc:
                    operator_codes.append(
                        OperatorCode(
                            source=source,
                            code=row[col],
                            operator=operator,
                        )
                    )

        names[slug] = operator

    to_create = [o for o in operators.values() if not o.slug]
    Operator.objects.bulk_create(to_create)
    OperatorCode.objects.bulk_create(operator_codes)


class Command(BaseCommand):
    def handle(self, **kwargs):
        code_sources = [
            (col, DataSource.objects.get_or_create(name=name)[0])
            for col, name in (
                ("NOCCODE", "National Operator Codes"),
                ("LO", "L"),
                ("SW", "SW"),
                ("WM", "WM"),
                ("WA", "W"),
                ("YO", "Y"),
                ("NW", "NW"),
                ("NE", "NE"),
                ("SC", "S"),
                ("SE", "SE"),
                ("EA", "EA"),
                ("EM", "EM"),
            )
        ]

        operators = Operator.objects.prefetch_related(
            "operatorcode_set", "licences"
        ).in_bulk()

        noc_csv(code_sources, operators)

        with open(settings.BASE_DIR / "fixtures" / "operators.yaml") as open_file:
            overrides = yaml.load(open_file, Loader=yaml.BaseLoader)

        names = set()

        url = "https://www.travelinedata.org.uk/noc/api/1.0/nocrecords.xml"
        response = requests.get(url)
        element = ET.fromstring(response.text)

        public_names = {}
        for e in element.find("PublicName"):
            e_id = e.findtext("PubNmId")
            assert e_id not in public_names
            public_names[e_id] = e

        # for e in element:
        #     print(e)

        operators_by_id = {}
        for e in element.find("Operators"):
            e_id = e.findtext("OpId")
            assert e_id not in operators_by_id
            operators_by_id[e_id] = e

        to_create = []
        to_update = []

        # noc_records = {}
        for e in element.find("NOCTable"):

            # e_id = e.findtext("PubNmId")
            # if e_id in noc_records:
            #     print(ET.tostring(noc_records[e_id]))
            #     print(ET.tostring(e))
            # noc_records[e_id] = e

            noc = e.findtext("NOCCODE").removeprefix("=")
            op = operators_by_id[e.findtext("OpId")]
            public_name = public_names[e.findtext("PubNmId")]

            assert e.findtext("OperatorPublicName") == public_name.findtext(
                "OperatorPublicName"
            )

            url = public_name.findtext("Website")
            if url:
                url = url.removesuffix("#")
                url = url.split("#")[-1]

            twitter = public_name.findtext("Twitter").removeprefix("@")

            if noc in overrides:
                if "url" in overrides[noc]:
                    url = overrides[noc]["url"]

                if "twitter" in overrides[noc]:
                    twitter = overrides[noc]["twitter"]

            if noc not in operators:
                # print(noc, e.findtext("OperatorPublicName"), e.findtext("VOSA_PSVLicenseName"), op.findtext("OpNm"))

                operators[noc] = Operator(
                    noc=noc, name=e.findtext("OperatorPublicName")
                )
                operator = operators[noc]

                operator.url = url
                operator.twitter = twitter

                if operator.name in names:
                    # duplicate name – save now to avoid slug collision
                    operator.save(force_insert=True)
                else:
                    # operator.slug = slugify(operator.name)
                    to_create.append(operator)

            else:
                operator = operators[noc]

                if operator.name != e.findtext("OperatorPublicName"):
                    print(
                        operator,
                        ET.tostring(e),
                        ET.tostring(op),
                        ET.tostring(public_name),
                    )

                # if operators[noc].name != public_name.findtext("OperatorPublicName"):
                # print(operators[noc], ET.tostring(public_name))

                if url != operator.url or twitter != operator.twitter:
                    operator.url = url
                    operator.twitter = twitter
                    to_update.append(operator)

            try:
                operator.clean_fields(exclude=["noc", "slug", "region"])
            except Exception as e:
                if "url" in e:
                    print(e, operator.url)
                    operator.url = ""
                else:
                    print(e)

            names.add(operator.name)

        Operator.objects.bulk_create(to_create)
        Operator.objects.bulk_update(to_update, ["url", "twitter", "name"])

        # licences = {}
        # for e in element.find("Licence"):
        #     e_id = e.findtext("OpId")
        #     if e_id in licences:
        #         print(ET.tostring(licences[e_id]), ET.tostring(e))
        #     licences[e_id] = e

        # print(public_names)

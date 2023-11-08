import xml.etree.ElementTree as ET

import requests
import yaml
from django.conf import settings
from django.core.management import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from vosa.models import Licence

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


def get_operator_codes(code_sources, noc, operator, noc_line):
    operator_codes = [
        OperatorCode(source=code_sources[0][1], code=noc, operator=operator)
    ]

    for col, source in code_sources[1:]:
        code = noc_line.find(col).text
        if code:
            code = code.removeprefix("=")
            if code != noc:
                operator_codes.append(
                    OperatorCode(
                        source=source,
                        code=code,
                        operator=operator,
                    )
                )
    return operator_codes


class Command(BaseCommand):
    @transaction.atomic()
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

        with open(settings.BASE_DIR / "fixtures" / "operators.yaml") as open_file:
            overrides = yaml.load(open_file, Loader=yaml.BaseLoader)

        operators_by_slug = {operator.slug: operator for operator in operators.values()}

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

        # operators_by_id = {}
        # for e in element.find("Operators"):
        #     e_id = e.findtext("OpId")
        #     assert e_id not in operators_by_id
        #     operators_by_id[e_id] = e

        noc_lines = {
            line.findtext("NOCCODE").removeprefix("="): line
            for line in element.find("NOCLines")
        }

        to_create = []
        to_update = []
        operator_codes = []
        licences = []

        for e in element.find("NOCTable"):
            noc = e.findtext("NOCCODE").removeprefix("=")

            if noc in noc_lines:
                noc_line = noc_lines[noc]
            else:
                print(noc)
                continue

            vehicle_mode = get_mode(noc_line.findtext("Mode"))
            if vehicle_mode == "airline":
                continue

            # op = operators_by_id[e.findtext("OpId")]
            public_name = public_names[e.findtext("PubNmId")]

            name = public_name.findtext("OperatorPublicName")

            url = public_name.findtext("Website")
            if url:
                url = url.removesuffix("#")
                url = url.split("#")[-1]

            twitter = public_name.findtext("Twitter").removeprefix("@")

            if noc in overrides:
                override = overrides[noc]

                if "url" in override:
                    url = override["url"]

                if "twitter" in override:
                    twitter = override["twitter"]

                if "name" in override:
                    if override["name"] == name:
                        print(name)
                    name = override["name"]

            if noc not in operators:
                # print(noc, e.findtext("OperatorPublicName"), e.findtext("VOSA_PSVLicenseName"), op.findtext("OpNm"))

                operators[noc] = Operator(
                    noc=noc,
                    name=name,
                    region_id=get_region_id(noc_line.findtext("TLRegOwn")),
                    vehicle_mode=vehicle_mode,
                )
                operator = operators[noc]

                slug = slugify(operator.name)
                if slug in operators_by_slug:
                    # duplicate name – save now to avoid slug collision
                    operator.save()
                    to_update.append(operator)
                else:
                    operator.slug = slug
                    to_create.append(operator)

                operators_by_slug[operator.slug or slug] = operator

                operator.url = url
                operator.twitter = twitter

                operator_codes += get_operator_codes(
                    code_sources, noc, operator, noc_line
                )
                try:
                    licences.append(
                        Operator.licences.through(
                            operator=operator,
                            licence=Licence.objects.get(
                                licence_number=noc_line.findtext("Licence")
                            ),
                        )
                    )
                except Licence.DoesNotExist:
                    pass

            else:
                operator = operators[noc]

                # if operator.name != name:
                #     print(operator.name, name)

                # if operators[noc].name != public_name.findtext("OperatorPublicName"):
                # print(operators[noc], ET.tostring(public_name))

                if (
                    name != operator.name
                    or url != operator.url
                    or twitter != operator.twitter
                    or vehicle_mode != operator.vehicle_mode
                ):
                    operator.name = name
                    operator.url = url
                    operator.twitter = twitter
                    operator.vehicle_mode = vehicle_mode
                    to_update.append(operator)

                if not operator.operatorcode_set.all():
                    operator_codes += get_operator_codes(
                        code_sources, noc, operator, noc_line
                    )

            try:
                operator.clean_fields(exclude=["noc", "slug", "region"])
            except Exception as e:
                if "url" in e.message_dict:
                    # print(e, operator.url)
                    operator.url = ""
                else:
                    print(noc, e)

        Operator.objects.bulk_create(to_create)
        Operator.objects.bulk_update(
            to_update, ["url", "twitter", "name", "vehicle_mode"]
        )

        OperatorCode.objects.bulk_create(operator_codes)
        Licence.objects.bulk_create(licences)

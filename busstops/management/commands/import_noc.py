import csv
import io
import xml.etree.ElementTree as ET

import requests
from django.core.management import BaseCommand

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


class Command(BaseCommand):
    def handle(self, **kwargs):
        url = "https://mytraveline.info/NOC/NOC_DB.csv"

        response = requests.get(url)

        operators = Operator.objects.prefetch_related(
            "operatorcode_set", "licences"
        ).in_bulk()

        to_update = []
        modes = set()

        for row in csv.DictReader(io.StringIO(response.text)):
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
                operator = Operator(
                    region_id=get_region_id(row["TLRegOwn"]), vehicle_mode=mode
                )
                operators[noc] = operator

            if noc == "AMSY":
                operator.name = row["RefNm"]
            else:
                operator.name = row["OperatorPublicName"]

            if not operator.noc:
                operator.noc = noc
                operator.save(force_insert=True)

        # Operator.objects.bulk_update(to_update, ["name"])

        return

        session = requests.Session()
        # session = requests_cache.CachedSession()
        url = "https://www.travelinedata.org.uk/noc/api/1.0/nocrecords.xml"
        response = session.get(url)
        element = ET.fromstring(response.text)

        public_names = {}
        for e in element.find("PublicName"):
            e_id = e.findtext("PubNmId")
            assert e_id not in public_names
            public_names[e_id] = e

        for e in element:
            print(e)

        operators_by_id = {}
        for e in element.find("Operators"):
            e_id = e.findtext("OpId")
            assert e_id not in operators_by_id
            operators_by_id[e_id] = e

        to_create = []

        # noc_records = {}
        for e in element.find("NOCTable"):

            if e.findtext("NOCCdQual"):
                print("\n\n")
                print(e.findtext("NOCCdQual"))
                print("\n\n")
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

            if noc not in operators:
                # print(noc, e.findtext("OperatorPublicName"), e.findtext("VOSA_PSVLicenseName"), op.findtext("OpNm"))

                operators[noc] = Operator(
                    noc=noc, name=e.findtext("OperatorPublicName")
                )

                to_create.append(operators[noc])

            else:
                if operators[noc].name != e.findtext("OperatorPublicName"):
                    print(
                        operators[noc],
                        ET.tostring(e),
                        ET.tostring(op),
                        ET.tostring(public_name),
                    )

                # if operators[noc].name != public_name.findtext("OperatorPublicName"):
                # print(operators[noc], ET.tostring(public_name))

                operators[noc].url = public_name.findtext("Website")

        Operator.objects.bulk_create(to_create)

        # licences = {}
        # for e in element.find("Licence"):
        #     e_id = e.findtext("OpId")
        #     if e_id in licences:
        #         print(ET.tostring(licences[e_id]), ET.tostring(e))
        #     licences[e_id] = e

        # print(public_names)

import xml.etree.cElementTree as ET
import requests
from django.core.management.base import BaseCommand

from busstops.models import Service, Trip


class Command(BaseCommand):
    @staticmethod
    def add_arguments(parser):
        parser.add_argument("url", type=str)
        parser.add_argument("api_key", type=str)

    def handle(self, url, api_key, *args, **options):
        response = requests.get(url, params={"api_key": api_key}, stream=True)
        response.raw.decode_content = True
        for _, element in ET.iterparse(response.raw):
            if element.tag[:29] == "{http://www.siri.org.uk/siri}":
                element.tag = element.tag[29:]

            if element.tag.endswith("PtSituationElement"):
                assert element.findtext("Consequences/Consequence/Condition") in (
                    "cancelled",
                    "altered",
                    "normalService",
                    "disrupted",
                )
                assert element.findtext("Consequences/Consequence/Severity") in (
                    "normal",
                    "unknown",
                )
                assert element.findtext("MiscellaneousReason") == "unknown"

                for avj in element.findall(
                    "Affects/VehicleJourneys/AffectedVehicleJourney"
                ):
                    line_name = avj.findtext("PublishedLineName")
                    operator_ref = avj.findtext("Operator/OperatorRef")
                    service = Service.objects.filter(
                        current=True, route__line_name=line_name, operator=operator_ref
                    ).distinct()
                    print(operator_ref, line_name)
                    print("  ", service)
                    if service:
                        journey_ref = avj.findtext("VehicleJourneyRef")
                        trips = Trip.objects.filter(
                            operator=operator_ref,
                            route__line_name=line_name,
                            ticket_machine_code=journey_ref,
                        )
                        print("  ", journey_ref, trips)

                element.clear()

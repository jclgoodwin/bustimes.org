import difflib
import xml.etree.cElementTree as ET
import requests

from datetime import timezone
from django.core.management.base import BaseCommand
from ciso8601 import parse_datetime

from busstops.models import Service, Trip, DataSource
from ...siri_sx import get_period
from ...models import Situation, AffectedJourney


def handle_situation(element, source, current_situations):
    situation_number = element.findtext("SituationNumber")

    situation = current_situations.get(situation_number)

    xml = ET.tostring(element, encoding="unicode")

    progress = element.findtext("Progress")
    assert progress in ("open", "closed"), progress

    if situation:
        if progress == "closed":
            situation.current = False
            situation.data = xml
            situation.save()
            return situation
        elif situation.data == xml:
            return situation

        # diff the XML to see why it changed
        for i in difflib.unified_diff(
            situation.data.splitlines(),
            xml.splitlines(),
            fromfile=situation.data,
            tofile=xml,
        ):
            print(i)
    elif progress == "closed":
        return

    if not situation:
        situation = Situation(
            source=source,
            situation_number=situation_number,
            current=(progress == "open"),
        )

    situation.data = xml
    situation.participant_ref = element.findtext("ParticipantRef")
    situation.reason = element.findtext("MiscellaneousReason")
    situation.created_at = parse_datetime(element.findtext("CreationTime"))
    # if created_at is naive, assume it's in UTC
    if not situation.created_at.tzinfo:
        situation.created_at = situation.created_at.replace(tzinfo=timezone.utc)

    vps = element.findall("ValidityPeriod")
    assert len(vps) == 1
    situation.publication_window = get_period(vps[0])

    situation.save()

    avjs = element.findall("Affects/VehicleJourneys/AffectedVehicleJourney")
    assert len(avjs) == 1
    avj = avjs[0]

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

        if len(trips) == 1:
            AffectedJourney.objects.update_or_create(
                {
                    "condition": element.findtext("Consequences/Consequence/Condition"),
                    "trip": trips[0],
                    "origin_departure_time": avj.findtext("OriginAimedDepartureTime"),
                },
                situation=situation,
            )
    return situation


class Command(BaseCommand):
    @staticmethod
    def add_arguments(parser):
        parser.add_argument("url", type=str)
        parser.add_argument("api_key", type=str)

    def handle(self, url, api_key, *args, **options):
        source = DataSource.objects.get_or_create(name="BODS cancellations")[0]

        response = requests.get(url, params={"api_key": api_key}, stream=True)
        response.raw.decode_content = True

        current_situations = {
            s.situation_number: s for s in source.situation_set.filter(current=True)
        }
        situations = []

        for _, element in ET.iterparse(response.raw):
            if element.tag[:29] == "{http://www.siri.org.uk/siri}":
                element.tag = element.tag[29:]

            if element.tag.endswith("PtSituationElement"):
                if situation := handle_situation(element, source, current_situations):
                    situations.append(situation.id)

                element.clear()

        # archive old situations
        print(
            source.situation_set.filter(current=True)
            .exclude(id__in=situations)
            .update(current=False)
        )

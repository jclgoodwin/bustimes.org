import difflib
import xml.etree.cElementTree as ET
import requests

from ciso8601 import parse_datetime
from datetime import timedelta, timezone
from django.core.management.base import BaseCommand
from django.db.transaction import atomic
from django.utils.timezone import localtime

from busstops.models import Trip, DataSource
from bustimes.utils import get_calendars
from ...siri_sx import get_period
from ...models import Situation, AffectedJourney, Call


def get_trip(avj):
    line_name = avj.findtext("PublishedLineName")
    operator_ref = avj.findtext("Operator/OperatorRef")

    print(operator_ref, line_name)

    journey_ref = avj.findtext("DatedVehicleJourneyRef") or avj.findtext(
        "VehicleJourneyRef"
    )
    departure_time = avj.findtext("OriginAimedDepartureTime")

    departure_time = parse_datetime(departure_time)
    departure_time = localtime(departure_time)

    trips = Trip.objects.filter(
        route__service__current=True,
        route__line_name=line_name,
        operator=operator_ref,
        ticket_machine_code=journey_ref,
        start=timedelta(hours=departure_time.hour, minutes=departure_time.minute),
        calendar__in=get_calendars(departure_time),
    )
    print("  ", journey_ref, trips)
    return trips


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

    avjs = element.findall("Affects/VehicleJourneys/AffectedVehicleJourney")
    assert len(avjs) == 1
    avj = avjs[0]

    trips = get_trip(avj)

    if len(trips) == 1:
        with atomic():
            situation.save()

            journey, created = AffectedJourney.objects.update_or_create(
                {
                    "condition": element.findtext("Consequences/Consequence/Condition"),
                    "trip": trips[0],
                    "origin_departure_time": avj.findtext("OriginAimedDepartureTime"),
                },
                situation=situation,
            )
            stop_times = journey.trip.stoptime_set.all()
            calls = avj.find("Calls")
            if len(calls) == len(stop_times):
                calls = [
                    Call(
                        journey=journey,
                        stop_time=stop_time,
                        arrival_time=call.findtext("AimedArrivalTime"),
                        departure_time=call.findtext("AimedDepartureTime"),
                        condition=call.findtext("CallCondition"),
                        order=call.findtext("Order"),
                    )
                    for stop_time, call in zip(stop_times, calls)
                    if stop_time.stop_id == call.findtext("StopPointRef")
                ]
                Call.objects.bulk_create(calls)
            else:
                print(f"  {len(calls)=} {len(stop_times)=}")

    if situation.id:
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

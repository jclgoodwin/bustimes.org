import logging
import xml.etree.cElementTree as ET
from ciso8601 import parse_datetime
from django.db.backends.postgresql.psycopg_any import DateTimeTZRange
from django.db.models import Q

import io
import xml.etree.cElementTree as ET
import zipfile

import requests

from busstops.models import DataSource, Operator, Service, StopPoint
from .models import Consequence, Link, Situation, ValidityPeriod


logger = logging.getLogger(__name__)


def get_period(element):
    start = element.find("StartTime").text
    end = element.findtext("EndTime")
    return DateTimeTZRange(start, end, "[]")


def get_operators(operator_ref):
    return Operator.objects.filter(
        operatorcode__code=operator_ref,
        operatorcode__source__name="National Operator Codes",
    )


def handle_item(item, source):
    situation_number = item.findtext("SituationNumber")

    item.find("Source/TimeOfCommunication").text = None

    xml = ET.tostring(item, encoding="unicode")

    created_time = parse_datetime(item.find("CreationTime").text)

    try:
        situation = Situation.objects.get(
            source=source, situation_number=situation_number
        )
        if situation.data == xml and situation.current:
            return situation.id  # hasn't changed
        created = False
        if not situation.current:
            situation.current = True
    except Situation.DoesNotExist:
        situation = Situation(
            source=source, situation_number=situation_number, current=True
        )
        created = True
    situation.data = xml
    situation.created = created_time
    situation.publication_window = get_period(item.find("PublicationWindow"))

    assert item.findtext("Progress") == "open"

    reason = item.findtext("MiscellaneousReason")
    if reason:
        situation.reason = reason

    situation.participant_ref = item.find("ParticipantRef").text
    situation.summary = item.find("Summary").text
    situation.text = item.find("Description").text
    situation.save()

    for i, link_element in enumerate(item.findall("InfoLinks/InfoLink/Uri")):
        link = Link(situation=situation)
        if not created and i == 0:
            try:
                link = situation.link_set.get()
            except Link.MultipleObjectsReturned:
                situation.link_set.all().delete()
            except Link.DoesNotExist:
                pass
        if link_element.text:
            link.url = link_element.text
            link.save()

    for i, period_element in enumerate(item.findall("ValidityPeriod")):
        period = ValidityPeriod(situation=situation)
        if not created and i == 0:
            try:
                period = situation.validityperiod_set.get()
            except ValidityPeriod.MultipleObjectsReturned:
                situation.validityperiod_set.all().delete()
            except ValidityPeriod.DoesNotExist:
                pass
        period.period = get_period(period_element)
        period.save()

    for i, consequence_element in enumerate(item.find("Consequences")):
        consequence = Consequence(situation=situation)
        if not created and i == 0:
            try:
                consequence = situation.consequence_set.get()
            except Consequence.MultipleObjectsReturned:
                situation.consequence_set.all().delete()
            except Consequence.DoesNotExist:
                pass

        consequence.text = consequence_element.find("Advice/Details").text
        consequence.data = ET.tostring(consequence_element, encoding="unicode")
        consequence.save()

        stops = consequence_element.findall("Affects/StopPoints/AffectedStopPoint")
        stops = [stop.find("StopPointRef").text for stop in stops]
        stops = StopPoint.objects.filter(atco_code__in=stops)
        consequence.stops.set(stops)

        consequence.services.clear()

        services = Service.objects.filter(current=True)
        stops_filter = Q(stops__in=stops)

        for line in consequence_element.findall(
            "Affects/Networks/AffectedNetwork/AffectedLine"
        ):
            line_name = line.findtext("PublishedLineName") or line.findtext("LineRef")
            line_name = line_name.replace("_", " ")
            line_filter = Q(route__line_name__iexact=line_name) | Q(
                line_name__iexact=line_name
            )
            for operator_ref in line.findall("AffectedOperator/OperatorRef"):
                operator_ref = operator_ref.text

                matching_services = services.filter(
                    line_filter, operator__in=get_operators(operator_ref)
                ).distinct()
                if len(matching_services) > 1:
                    matching_services = matching_services.filter(stops_filter)

                if matching_services:
                    consequence.services.add(*matching_services)
                else:
                    logger.info(f"{situation_number=} {operator_ref=} {line_name=}")

        for operator in consequence_element.findall(
            "Affects/Operators/AffectedOperator"
        ):
            operator_ref = operator.findtext("OperatorRef")
            try:
                consequence.operators.add(*get_operators(operator_ref))
            except Operator.DoesNotExist as e:
                logger.exception(e)

    return situation.id


def bods_disruptions():
    url = "https://data.bus-data.dft.gov.uk/disruptions/download/bulk_archive"

    source = DataSource.objects.get_or_create(name="Bus Open Data")[0]

    situations = []

    response = requests.get(url, timeout=61)
    assert response.ok
    archive = zipfile.ZipFile(io.BytesIO(response.content))

    namelist = archive.namelist()
    assert len(namelist) == 1
    open_file = archive.open(namelist[0])

    for _, element in ET.iterparse(open_file):
        if element.tag[:29] == "{http://www.siri.org.uk/siri}":
            element.tag = element.tag[29:]

        if element.tag.endswith("PtSituationElement"):
            situations.append(handle_item(element, source))
            element.clear()

    source.situation_set.filter(current=True).exclude(id__in=situations).update(
        current=False
    )

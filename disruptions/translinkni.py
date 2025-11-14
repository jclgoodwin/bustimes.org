import logging
from django.db.backends.postgresql.psycopg_any import DateTimeTZRange
from django.db.models import Q

from bs4 import BeautifulSoup

import requests

from busstops.models import DataSource, Service
from .models import Consequence, Situation, ValidityPeriod


logger = logging.getLogger(__name__)


def get_period(element: dict):
    start = element.get("from")
    end = element.get("to")
    return DateTimeTZRange(start, end, "[]")


def handle_item(item: dict, source: DataSource, current_situations: dict):
    situation_number = item["id"]

    situation = current_situations.get(situation_number)

    if situation:
        # return situation.id  # hasn't changed
        created = False
    else:
        situation = Situation(
            source=source, situation_number=situation_number, current=True
        )
        created = True

    situation.created_at = item["timestamps"]["creation"]
    situation.modified_at = item["timestamps"]["lastModification"]
    situation.publication_window = get_period(item["timestamps"]["availability"])

    assert len(item["infoLinks"]) == 1

    situation.summary = item["infoLinks"][0]["urlText"]

    if "content" not in item["infoLinks"][0]:
        return

    assert (
        item["infoLinks"][0]["urlText"]
        == item["infoLinks"][0]["title"]
        == item["infoLinks"][0]["subtitle"]
    )
    situation.text = item["infoLinks"][0]["content"]
    soup = BeautifulSoup(situation.text, "lxml")
    situation.text = soup.get_text().strip().replace("\n\xa0\n", "\n\n")
    situation.save()

    for i, period_element in enumerate(item["timestamps"]["validity"]):
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

    consequence = Consequence(situation=situation)
    if not created and i == 0:
        try:
            consequence = situation.consequence_set.get()
        except Consequence.MultipleObjectsReturned:
            situation.consequence_set.all().delete()
        except Consequence.DoesNotExist:
            pass

    if consequence.id:
        consequence.services.clear()

    services = Service.objects.filter(current=True)

    if "lines" in item["affected"]:
        for line in item["affected"]["lines"]:
            line_name = line["number"]
            line_filter = Q(route__line_name__iexact=line_name) | Q(
                line_name__iexact=line_name
            )
            operator_ref = line["operator"]["id"]

            matching_services = services.filter(
                line_filter, operator=operator_ref
            ).distinct()

            if matching_services:
                if not consequence.id:
                    consequence.save()

                consequence.services.add(*matching_services)

    return situation.id


def translink_disruptions(api_key):
    url = "https://opendata.translinkniplanner.co.uk/Ext_API/XML_ADDINFO_REQUEST?ext_macro=addinfo"

    source = DataSource.objects.get_or_create(name="Translink")[0]

    situations = []

    response = requests.get(url, headers={"x-api-token": api_key}, timeout=61)

    elements = response.json()["infos"]["current"]

    situation_numbers = [element["id"] for element in elements]

    current_situations = {
        s.situation_number: s
        for s in source.situation_set.filter(situation_number__in=situation_numbers)
    }

    for element in elements:
        if situation_id := handle_item(element, source, current_situations):
            situations.append(situation_id)
    source.situation_set.filter(current=True).exclude(id__in=situations).update(
        current=False
    )

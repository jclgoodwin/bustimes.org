import logging
from hashlib import sha256

import requests
from django.conf import settings
from django.db.backends.postgresql.psycopg_any import DateTimeTZRange
from django.db.models import Q

from busstops.models import DataSource, Service, StopPoint

from .models import Consequence, Situation, ValidityPeriod

logger = logging.getLogger(__name__)


def get_hash(text):
    return sha256(text.encode()).hexdigest()[:36]


def tfl_disruptions():
    session = requests.Session()
    session.headers.update({"User-Agent": "bustimes.org"})

    source = DataSource.objects.get_or_create(name="TfL")[0]

    situations = set()

    response = session.get(
        "https://api.tfl.gov.uk/StopPoint/Mode/bus/Disruption",
        params=settings.TFL,
        timeout=30,
    )

    for item in response.json():
        stops = (
            StopPoint.objects.filter(
                Q(atco_code=item["atcoCode"]) | Q(stop_area=item["atcoCode"])
            )
            .only("atco_code")
            .order_by()
        )

        if not stops:
            continue

        window = DateTimeTZRange(item["fromDate"], item["toDate"], "[]")

        situation_number = get_hash(f"{item['description']} {window}")

        situation = Situation.objects.filter(
            source=source, situation_number=situation_number
        ).first()

        if not situation:
            situation = Situation(
                situation_number=situation_number,
                created=item["fromDate"],
                source=source,
            )
        situation.current = True
        situation.text = item["description"].replace("\\n", "\n").strip()
        if ": " in situation.text:
            situation.summary, situation.text = situation.text.split(": ", 1)
        else:
            situation.reason = item["type"]
        situation.text = situation.text.replace(". ", ".\n\n")
        situation.publication_window = window
        situation.reason = item["type"]
        situation.save()

        try:
            consequence = situation.consequence_set.get()
        except Consequence.DoesNotExist:
            consequence = Consequence(situation=situation)
            consequence.save()

        consequence.stops.add(*stops)

        try:
            period = situation.validityperiod_set.get()
        except ValidityPeriod.DoesNotExist:
            period = ValidityPeriod(situation=situation, period=window)
            period.save()

        situations.add(situation.id)

    response = session.get(
        "https://api.tfl.gov.uk/Line/Mode/bus/Status",
        params=settings.TFL,
        timeout=30,
    )

    for item in response.json():
        if item["lineStatuses"][0]["statusSeverityDescription"] == "Good Service":
            assert len(item["lineStatuses"]) == 1
            continue

        services = Service.objects.only("id").filter(
            line_name__iexact=item["name"], region="L", current=True, mode="bus"
        )
        if not services:
            continue
        elif len(services) > 1:
            print(f"multiple {item['name']}s: {services}")

        for status in item["lineStatuses"]:
            assert status["reason"] == status["disruption"]["description"]

            validity_periods = status["validityPeriods"]

            window = DateTimeTZRange(
                min(period["fromDate"] for period in validity_periods),
                max(period["toDate"] for period in validity_periods),
                "[]",
            )

            situation_number = get_hash(f"{status['reason']} {window}")

            situation = Situation.objects.filter(
                source=source, situation_number=situation_number
            ).first()
            if not situation:
                situation = Situation(
                    situation_number=situation_number,
                    text=status["reason"],
                    created=status["disruption"]["created"],
                    publication_window=window,
                    source=source,
                )
                created = True
            else:
                created = False

            if ": " in situation.text and situation.text.index(": ") < 255:
                situation.summary, situation.text = situation.text.split(": ", 1)

            situation.text = situation.text.replace(". ", ".\n\n")

            situation.current = True
            situation.save()

            if created:
                for period in validity_periods:
                    window = DateTimeTZRange(period["fromDate"], period["toDate"], "[]")
                    vp = ValidityPeriod(
                        situation=situation,
                        period=window,
                    )
                    vp.save()

            consequence = situation.consequence_set.first()
            if not consequence:
                consequence = Consequence(situation=situation)
                consequence.save()

            consequence.services.add(*services)

            situations.add(situation.id)

    old_situations = source.situation_set.filter(Q(current=True), ~Q(id__in=situations))
    old_situations.update(current=False)

import logging
from hashlib import sha256

import requests
from django.core.management.base import BaseCommand
from django.db.models import Q
from psycopg2.extras import DateTimeTZRange

from busstops.models import DataSource, Service, StopPoint

from ...models import Consequence, Situation, ValidityPeriod

logger = logging.getLogger(__name__)


def get_hash(text):
    return sha256(text.encode()).hexdigest()[:36]


class Command(BaseCommand):
    def fetch(self):
        session = requests.Session()

        source = DataSource.objects.get_or_create(name="TfL")[0]

        situations = set()

        response = session.get(
            "https://api.tfl.gov.uk/StopPoint/mode/bus/Disruption", timeout=10
        )

        for item in response.json():

            stops = StopPoint.objects.filter(
                Q(atco_code=item["atcoCode"]) | Q(stop_area=item["atcoCode"])
            )

            if not stops:
                continue

            situation_number = get_hash(item["description"])

            window = DateTimeTZRange(item["fromDate"], item["toDate"], "[]")

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
            situation.text = item["description"].replace("\\n", "\n")
            situation.publication_window = window
            situation.summary = item["type"]
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
            "https://api.tfl.gov.uk/line/mode/bus/status", timeout=10
        )

        for item in response.json():

            if item["lineStatuses"][0]["statusSeverityDescription"] == "Good Service":
                assert len(item["lineStatuses"]) == 1
                continue

            try:
                service = Service.objects.get(
                    line_name__iexact=item["name"], region="L", current=True
                )
            except Service.DoesNotExist as e:
                logger.error(e)
                continue

            for status in item["lineStatuses"]:
                assert status["reason"] == status["disruption"]["description"]

                assert len(status["validityPeriods"]) == 1

                window = DateTimeTZRange(
                    status["validityPeriods"][0]["fromDate"],
                    status["validityPeriods"][0]["toDate"],
                    "[]",
                )
                assert len(status["validityPeriods"]) == 1

                situation_number = get_hash(status["reason"])

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
                situation.current = True
                situation.save()

                for period in status["validityPeriods"]:
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

                consequence.services.add(service)

                situations.add(situation.id)

        old_situations = source.situation_set.filter(
            Q(current=True), ~Q(id__in=situations)
        )
        old_situations.update(current=False)

    def handle(self, *args, **options):
        self.fetch()

import requests
from django.core.management.base import BaseCommand

from busstops.models import DataSource, Operator, OperatorCode


class Command(BaseCommand):
    def handle(self, **options):
        source, _ = DataSource.objects.get_or_create(name="MyTrip")

        session = requests.Session()
        session.headers.update({"x-api-key": source.settings["x-api-key"]})

        response = session.get(
            "https://mytrip-bustimes.api.passengercloud.com/ticketing/topups"
        )

        items = response.json()["_embedded"]["topup:category"]

        for item in items:
            name = item["title"]
            code = item["id"]

            if OperatorCode.objects.filter(code=code, source=source).exists():
                print("✔️ ", name)
                continue

            try:
                operator = Operator.objects.get(name=name)
            except (Operator.DoesNotExist, Operator.MultipleObjectsReturned) as e:
                print(name, e)
                operator = None
                while operator is None:
                    operator_id = input("Enter NOC: ").upper()
                    try:
                        operator = Operator.objects.get(noc=operator_id)
                    except Operator.DoesNotExist as e:
                        print(e)

            print("✔️ ", operator, name)
            OperatorCode.objects.create(operator=operator, code=code, source=source)

        codes = [item["id"] for item in items]
        to_delete = OperatorCode.objects.filter(source=source).exclude(code__in=codes)
        if to_delete:
            print(f"{to_delete=}")
            print(to_delete.delete())

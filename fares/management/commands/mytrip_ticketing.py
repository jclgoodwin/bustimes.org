import requests
from django.core.management.base import BaseCommand

from busstops.models import DataSource, Operator, OperatorCode


class Command(BaseCommand):
    @staticmethod
    def add_arguments(parser):
        parser.add_argument("api_key", type=str, nargs="?")

    def handle(self, api_key, **options):
        source, _ = DataSource.objects.get_or_create(name="MyTrip")
        if api_key:
            source.settings = {"x-api-key": api_key}
        print(source.settings)

        session = requests.Session()
        session.headers.update({"x-api-key": source.settings["x-api-key"]})

        response = session.get(
            "https://mytrip-bustimes.api.passengercloud.com/ticketing/topups"
        )

        print(response)
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
                operator_id = input(f"{e} {name}. Manually enter NOC: ").upper()
                try:
                    OperatorCode.objects.create(
                        operator_id=operator_id, code=code, source=source
                    )
                except Exception as e:
                    print(e)
            else:
                print("✔️ ", operator, name)
                OperatorCode.objects.create(operator=operator, code=code, source=source)

        codes = [item["id"] for item in items]
        to_delete = OperatorCode.objects.filter(source=source).exclude(code__in=codes)
        if to_delete:
            print(f"{to_delete=}")
            print(to_delete.delete())

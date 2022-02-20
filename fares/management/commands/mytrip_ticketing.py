import requests
from django.core.management.base import BaseCommand
from busstops.models import Operator, OperatorCode, DataSource


class Command(BaseCommand):
    @staticmethod
    def add_arguments(parser):
        parser.add_argument('api_key', type=str)

    def handle(self, api_key, **options):
        source, _ = DataSource.objects.get_or_create(name="MyTrip")

        session = requests.Session()
        session.headers.update({
                'x-api-key': api_key
            })

        response = session.get("https://mytrip-bustimes.api.passengercloud.com/ticketing/topups")

        for item in response.json()["_embedded"]["topup:category"]:
            name = item["title"]
            code = item["id"]

            if OperatorCode.objects.filter(code=code, source=source).exists():
                print('✔️ ', name)
                continue

            try:
                operator = Operator.objects.get(name=name)
            except (Operator.DoesNotExist, Operator.MultipleObjectsReturned) as e:
                operator_id = input(f"{e} {name}. Manually enter NOC: ").upper()
                try:
                    OperatorCode.objects.create(operator_id=operator_id, code=code, source=source)
                except Exception as e:
                    print(e)
            else:
                print('✔️ ', operator, name)
                OperatorCode.objects.create(operator=operator, code=code, source=source)

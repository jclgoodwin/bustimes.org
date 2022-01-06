import requests
from django.core.management.base import BaseCommand
# from django.contrib.gis.geos import Point, LineString, MultiLineString
# from bustimes.models import Trip
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
            try:
                operator = Operator.objects.get(name=item["title"])
            except (Operator.DoesNotExist, Operator.MultipleObjectsReturned) as e:
                print('❌ ', item["title"], e)
            else:
                print('✔️ ', operator)
                OperatorCode.objects.get_or_create(operator=operator, code=item["id"], source=source)

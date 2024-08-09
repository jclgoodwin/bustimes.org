import requests
import json
from datetime import datetime
from django.core.management.base import BaseCommand
from pygments import highlight
from pygments.formatters import TerminalFormatter
from pygments.lexers import JsonLexer
from time import sleep
from busstops.models import Service
from .import_transxchange import get_open_data_operators


class Command(BaseCommand):
    @staticmethod
    def add_arguments(parser):
        parser.add_argument("api_key", type=str)

    def handle(self, api_key, **options):
        assert len(api_key) == 40

        open_data_operators, incomplete_operators = get_open_data_operators()

        session = requests.Session()

        formatter = TerminalFormatter()

        url = "https://data.bus-data.dft.gov.uk/api/v1/dataset/"
        params = {
            "api_key": api_key,
            "status": ["published"],
            "limit": 100,
            "modifiedDate": "2023-01-01T00:00:00",
            "endDateStart": datetime.now().isoformat(),
        }
        while url:
            response = session.get(url, params=params)
            print(response.url)
            data = response.json()
            for item in data["results"]:
                if Service.objects.filter(
                    operator__in=item["noc"], current=True
                ).exists():
                    continue
                if any(noc in open_data_operators for noc in item["noc"]):
                    continue
                del item["localities"]
                print(highlight(json.dumps(item, indent=4), JsonLexer(), formatter))
            url = data["next"]
            params = None
            if url:
                sleep(1)

import requests
from django.core.management.base import BaseCommand
from time import sleep
from .import_transxchange import get_open_data_operators


class Command(BaseCommand):
    @staticmethod
    def add_arguments(parser):
        parser.add_argument('api_key', type=str)

    def handle(self, api_key, **options):
        assert len(api_key) == 40

        open_data_operators, incomplete_operators = get_open_data_operators()

        session = requests.Session()

        url = 'https://data.bus-data.dft.gov.uk/api/v1/dataset/'
        params = {
            'api_key': api_key,
            'status': ['published', 'expiring'],
        }
        while url:
            response = session.get(url, params=params)
            data = response.json()
            for item in data['results']:
                if any(noc in open_data_operators for noc in item['noc']):
                    continue
                print(item['name'])
                print(' ', item['noc'])
                print(' ', item['description'])
                print(' ', item['comment'])
            url = data['next']
            params = None
            if url:
                sleep(1)

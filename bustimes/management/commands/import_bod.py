"""Import timetable data "fresh from the cow"
"""

from requests import Session
from ciso8601 import parse_datetime
from django.core.management.base import BaseCommand
from busstops.models import DataSource, Service
from .import_gtfs import download_if_modified
from .import_transxchange import Command as TransXChangeCommand
from ...models import Route


class Command(BaseCommand):
    @staticmethod
    def add_arguments(parser):
        parser.add_argument('api_key', nargs=1, type=str)

    def handle(self, api_key, **options):
        command = TransXChangeCommand()
        command.undefined_holidays = set()
        command.notes = {}
        command.corrections = {}

        session = Session()

        command.operators = {
            'CO': 'LYNX'
        }
        command.region_id = 'EA'
        command.service_descriptions = {}
        command.service_codes = set()
        command.calendar_cache = {}

        response = session.get('https://data.bus-data.dft.gov.uk/api/v1/dataset/', params={
            'api_key': api_key,
            'noc': 'LYNX',
        })

        sources = []

        for result in response.json()['results']:
            if result['status'] == 'published':
                path = result['name']
                url = result['url']
                modified = download_if_modified(path, url)
                print(modified, path)

                command.source, created = DataSource.objects.get_or_create({'name': path}, url=url)
                print(command.source.datetime)
                if not created:
                    command.source.name = path
                command.source.datetime = parse_datetime(result['modified'])
                sources.append(command.source)

                with open(path) as open_file:
                    command.handle_file(open_file, path)

        print(Route.objects.filter(service__operator='LYNX').exclude(source__in=sources).delete())
        print(Service.objects.filter(operator='LYNX', current=True, route=None).update(current=False))

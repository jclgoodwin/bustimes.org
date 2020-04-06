"""Import timetable data "fresh from the cow"
"""
import os
from requests import Session
from ciso8601 import parse_datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from busstops.models import DataSource, Service
from .import_gtfs import download_if_modified
from .import_transxchange import Command as TransXChangeCommand
from .import_passenger import handle_file
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

        for operator_id, region_id, operators in settings.BOD_OPERATORS:
            command.operators = operators
            command.region_id = region_id
            command.service_descriptions = {}
            command.service_codes = set()
            command.calendar_cache = {}

            response = session.get('https://data.bus-data.dft.gov.uk/api/v1/dataset/', params={
                'api_key': api_key,
                'noc': operator_id
            })

            sources = []

            for result in response.json()['results']:
                if result['status'] == 'published':
                    filename = result['name']
                    url = result['url']
                    path = os.path.join(settings.DATA_DIR, filename)
                    modified = download_if_modified(path, url)
                    print(modified, path)

                    command.source, created = DataSource.objects.get_or_create({'name': filename}, url=url)
                    print(command.source.datetime)
                    if not created:
                        command.source.name = filename
                    command.source.datetime = parse_datetime(result['modified'])
                    sources.append(command.source)

                    handle_file(command, filename)
                    print(result)

                    command.source.save(update_fields=['name', 'datetime'])

            print(Route.objects.filter(service__operator__in=operators.values()).exclude(source__in=sources).delete())
            print(Service.objects.filter(operator__in=operators.values(), current=True,
                                         route=None).update(current=False))

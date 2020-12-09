"""Import timetable data "fresh from the cow"
"""
import os
import logging
import requests
import zipfile
import xml.etree.cElementTree as ET
from io import StringIO
from ciso8601 import parse_datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import DataError
from django.utils import timezone
from busstops.models import DataSource, Operator, Service
from .import_transxchange import Command as TransXChangeCommand
from ...utils import download, download_if_changed
from ...models import Route, Calendar


logger = logging.getLogger(__name__)
session = requests.Session()


def clean_up(operators, sources, incomplete=False):
    routes = Route.objects.filter(service__operator__in=operators).exclude(source__in=sources)
    if incomplete:
        routes = routes.exclude(source__url__contains='.tnds.')
    routes.delete()
    Service.objects.filter(operator__in=operators, current=True, route=None).update(current=False)
    Calendar.objects.filter(trip=None).delete()


def get_command():
    command = TransXChangeCommand()
    command.undefined_holidays = set()
    command.missing_operators = []
    command.notes = {}
    command.corrections = {}

    return command


def handle_file(command, path):
    # the downloaded file might be plain XML, or a zipped archive - we just don't know yet
    try:
        with zipfile.ZipFile(os.path.join(settings.DATA_DIR, path)) as archive:
            for filename in archive.namelist():
                if filename.endswith('.csv'):
                    continue
                with archive.open(filename) as open_file:
                    qualified_filename = os.path.join(path, filename)
                    try:
                        try:
                            command.handle_file(open_file, qualified_filename)
                        except ET.ParseError:
                            open_file.seek(0)
                            content = open_file.read().decode('utf-16')
                            fake_file = StringIO(content)
                            command.handle_file(fake_file, qualified_filename)
                    except (ET.ParseError, ValueError, AttributeError, DataError) as e:
                        logger.error(e, exc_info=True)
    except zipfile.BadZipFile:
        with open(os.path.join(settings.DATA_DIR, path)) as open_file:
            try:
                command.handle_file(open_file, path)
            except (AttributeError, DataError) as e:
                logger.error(e, exc_info=True)


def bus_open_data(api_key, operator):
    command = get_command()

    for operator_id, region_id, operators, incomplete in settings.BOD_OPERATORS:
        if operator and operator_id != operator:
            continue

        datasets = []

        url = 'https://data.bus-data.dft.gov.uk/api/v1/dataset/'
        params = {
            'api_key': api_key,
            'status': ['published', 'expiring']
        }
        if operator_id.isupper():
            params['noc'] = operator_id
        else:
            params['search'] = operator_id

        while url:
            response = session.get(url, params=params)
            json = response.json()
            for dataset in json['results']:
                dataset['source'], created = DataSource.objects.get_or_create(url=dataset['url'])
                dataset['modified'] = parse_datetime(dataset['modified'])
                datasets.append(dataset)
            url = json['next']
            params = None

        if any(dataset['source'].datetime != dataset['modified'] for dataset in datasets):
            command.operators = operators
            command.region_id = region_id
            command.service_descriptions = {}
            command.service_ids = set()
            command.route_ids = set()
            command.calendar_cache = {}

            sources = []

            for dataset in datasets:
                filename = dataset['name']
                url = dataset['url']
                path = os.path.join(settings.DATA_DIR, filename)

                command.source = dataset['source']

                print(response.url, filename)
                command.source.name = filename
                command.source.datetime = dataset['modified']
                download(path, url)
                handle_file(command, filename)

                command.source.save(update_fields=['name', 'datetime'])

                print(' ', Operator.objects.filter(service__route__source=command.source).distinct().values('id'))

                command.update_geometries()
                command.mark_old_services_as_not_current()

                sources.append(command.source)

            if operators:
                operators = operators.values()
            else:
                operators = [operator_id]

            if Service.objects.filter(source__in=sources, operator__in=operators).exists():
                clean_up(operators, sources, incomplete)

    command.debrief()


def ticketer(operator=None):
    command = get_command()

    for region_id, operators, name in settings.TICKETER_OPERATORS:
        noc = operators[0]

        if operator and operator != noc:
            continue

        url = f'https://opendata.ticketer.com/uk/{noc}/routes_and_timetables/current.zip'
        filename = f'{noc}.zip'
        path = os.path.join(settings.DATA_DIR, filename)
        command.source, created = DataSource.objects.get_or_create({'name': name}, url=url)

        modified, last_modified = download_if_changed(path, url)

        if modified or operator == noc:
            print(url, last_modified)

            command.operators = {code: code for code in operators}
            if noc == 'GOEA':
                command.operators['GEA'] = 'KCTB'
            elif noc == 'ACYM':
                command.operators['ANW'] = noc
            elif noc == 'AMID':
                command.operators['AMD'] = noc
            elif noc == 'AMTM':
                command.operators['ASC'] = noc

            command.region_id = region_id
            command.service_descriptions = {}
            command.service_ids = set()
            command.route_ids = set()
            command.calendar_cache = {}

            # avoid importing old data
            command.source.datetime = timezone.now()

            handle_file(command, filename)

            command.update_geometries()
            command.mark_old_services_as_not_current()

            clean_up(operators, [command.source])

            command.source.datetime = last_modified
            command.source.save(update_fields=['datetime'])

            print(' ', command.source.route_set.order_by('end_date').distinct('end_date').values('end_date'))
            print(' ', {o['id']: o['id'] for o in
                  Operator.objects.filter(service__route__source=command.source).distinct().values('id')})

    command.debrief()


def stagecoach(operator=None):
    command = get_command()

    for region_id, noc, name, operators in settings.STAGECOACH_OPERATORS:
        if operator and operator != noc:  # something like 'sswl'
            continue

        filename = f'stagecoach-{noc}-route-schedule-data-transxchange.zip'
        url = f'https://opendata.stagecoachbus.com/{filename}'
        path = os.path.join(settings.DATA_DIR, filename)

        command.source, created = DataSource.objects.get_or_create({'name': name}, url=url)

        modified, last_modified = download_if_changed(path, url)

        if modified and command.source.datetime and command.source.datetime >= last_modified:
            modified = False

        if modified or operator:
            print(url, last_modified)

            command.operators = operators
            command.region_id = region_id
            command.service_descriptions = {}
            command.service_ids = set()
            command.route_ids = set()
            command.calendar_cache = {}

            # avoid importing old data
            command.source.datetime = timezone.now()

            handle_file(command, filename)

            command.update_geometries()
            command.mark_old_services_as_not_current()

            clean_up(command.operators.values(), [command.source])

            command.source.datetime = last_modified
            command.source.save(update_fields=['datetime'])

            print(' ', command.source.route_set.order_by('end_date').distinct('end_date').values('end_date'))
            operators = Operator.objects.filter(service__route__source=command.source).distinct().values('id')
            operators = {o['id']: o['id'] for o in operators}
            print(' ', operators)
            if 'ANEA' in operators or 'OXBC' in operators:
                print(command.source.service_set.filter(operator__in=['ANEA', 'OXBC']).delete())

    command.debrief()


class Command(BaseCommand):
    @staticmethod
    def add_arguments(parser):
        parser.add_argument('api_key', type=str)
        parser.add_argument('operator', type=str, nargs='?')

    def handle(self, api_key, operator, **options):
        if api_key == 'stagecoach':
            stagecoach(operator)
        elif api_key == 'ticketer':
            ticketer(operator)
        else:
            bus_open_data(api_key, operator)

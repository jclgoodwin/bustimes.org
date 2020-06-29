"""Import timetable data "fresh from the cow"
"""
import os
import logging
import requests
import zipfile
import xml.etree.cElementTree as ET
from ciso8601 import parse_datetime
from django.core.management.base import BaseCommand
from django.conf import settings
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
                    try:
                        command.handle_file(open_file, os.path.join(path, filename))
                    except (ET.ParseError, ValueError) as e:
                        print(filename)
                        logger.error(e, exc_info=True)
    except zipfile.BadZipFile:
        with open(os.path.join(settings.DATA_DIR, path)) as open_file:
            command.handle_file(open_file, path)


def bus_open_data(api_key):
    command = get_command()

    for operator_id, region_id, operators, incomplete in settings.BOD_OPERATORS:
        command.operators = operators
        command.region_id = region_id
        command.service_descriptions = {}
        command.service_ids = set()
        command.calendar_cache = {}

        sources = []

        url = 'https://data.bus-data.dft.gov.uk/api/v1/dataset/'
        params = {
            'api_key': api_key,
            'noc': operator_id,
            'status': ['published', 'expiring']
        }

        while url:
            response = session.get(url, params=params)
            json = response.json()

            for result in json['results']:
                filename = result['name']
                url = result['url']
                path = os.path.join(settings.DATA_DIR, filename)

                modified = parse_datetime(result['modified'])

                command.source, created = DataSource.objects.get_or_create({'name': filename}, url=url)

                if command.source.datetime != modified:
                    print(response.url, filename)
                    command.source.datetime = modified
                    download(path, url)
                    handle_file(command, filename)

                    if not created:
                        command.source.name = filename
                    command.source.save(update_fields=['name', 'datetime'])

                    print(' ', Operator.objects.filter(service__route__source=command.source).distinct().values('id'))

                    command.mark_old_services_as_not_current()

                sources.append(command.source)

            url = json['next']
            params = None

        if sources:
            clean_up(operators.values(), sources, incomplete)


def first():
    command = get_command()

    url_prefix = 'http://travelinedatahosting.basemap.co.uk/data/first/'
    sources = DataSource.objects.filter(url__startswith=url_prefix)

    for operator, region_id, operators in settings.FIRST_OPERATORS:
        filename = operator + '.zip'
        url = url_prefix + filename
        modified, last_modified = download_if_changed(os.path.join(settings.DATA_DIR, filename), url)

        if modified:
            print(url)

            command.operators = operators
            command.region_id = region_id
            command.service_descriptions = {}
            command.service_ids = set()
            command.calendar_cache = {}

            command.source, created = DataSource.objects.get_or_create({'name': operator}, url=url)
            command.source.datetime = timezone.now()

            handle_file(command, filename)

            command.mark_old_services_as_not_current()

            clean_up(operators.values(), sources)

            command.source.datetime = last_modified
            command.source.save(update_fields=['datetime'])

            print(' ', command.source.route_set.order_by('end_date').distinct('end_date').values('end_date'))
            print(' ', Operator.objects.filter(service__route__source=command.source).distinct().values('id'))


def stagecoach():
    command = get_command()

    for region_id, noc, operator, operators in settings.STAGECOACH_OPERATORS:
        filename = f'stagecoach-{noc}-route-schedule-data-transxchange.zip'
        url = f'https://opendata.stagecoachbus.com/{filename}'
        path = os.path.join(settings.DATA_DIR, filename)

        command.source, created = DataSource.objects.get_or_create({'name': operator}, url=url)

        modified, last_modified = download_if_changed(path, url)

        if modified and command.source.datetime and command.source.datetime >= last_modified:
            modified = False

        if modified:
            print(url)

            command.operators = operators
            command.region_id = region_id
            command.service_descriptions = {}
            command.service_ids = set()
            command.calendar_cache = {}

            # avoid importing old data
            command.source.datetime = timezone.now()

            handle_file(command, filename)

            command.mark_old_services_as_not_current()

            clean_up(command.operators.values(), [command.source])

            command.source.datetime = last_modified
            command.source.save(update_fields=['datetime'])

            print(' ', command.source.route_set.order_by('end_date').distinct('end_date').values('end_date'))
            print(' ', {o['id']: o['id'] for o in
                  Operator.objects.filter(service__route__source=command.source).distinct().values('id')})


class Command(BaseCommand):
    @staticmethod
    def add_arguments(parser):
        parser.add_argument('api_key', type=str)

    def handle(self, api_key, **options):

        stagecoach()

        bus_open_data(api_key)

        first()

"""Import timetable data "fresh from the cow"
"""

import os
import requests
import zipfile
from time import sleep
from datetime import timedelta
from requests_html import HTMLSession
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone, dateparse
from busstops.models import DataSource, Service, ServiceColour
from .import_bod import handle_file
from .import_transxchange import Command as TransXChangeCommand
from .import_gtfs import read_file
from ...utils import write_file
from ...models import Route, Calendar


def download_if_new(path, url):
    if not os.path.exists(path):
        response = requests.get(url, stream=True)
        write_file(path, response)
        return True
    return False


def handle_gtfs(operators, path):
    operator = operators[0]
    with zipfile.ZipFile(path) as archive:
        for line in read_file(archive, 'routes.txt'):
            foreground = line['route_text_color']
            background = line['route_color']
            if foreground == '000000' and background == 'FFFFFF':
                continue
            try:
                service = Service.objects.get(operator__in=operators, line_name=line['route_short_name'], current=True)
            except (Service.DoesNotExist, Service.MultipleObjectsReturned):
                continue
            colour, _ = ServiceColour.objects.get_or_create(
                {'name': service.line_brand},
                foreground=f"#{foreground}",
                background=f"#{background}",
                operator_id=operator,
            )
            service.colour = colour
            service.save(update_fields=['colour'])


def get_versions(session, url):
    versions = []
    try:
        response = session.get(url, timeout=5)
    except requests.RequestException as e:
        print(url, e)
        sleep(5)
        return
    if not response.ok:
        print(url, response)
        sleep(5)
        return
    for element in response.html.find():
        if element.tag == 'h3':
            heading = element.text
        elif element.tag == 'a':
            url = element.attrs['href']
            if '/txc/' in url:
                url = element.attrs['href']
                filename = url.split('/')[-1]
                path = os.path.join(settings.DATA_DIR, filename)
                modified = download_if_new(path, url)
                gtfs_path = f'{path[:-3]}gtfs.zip'
                download_if_new(gtfs_path, url.replace('/txc/', '/gtfs/'))
                dates = heading.split(' to ')
                versions.append({
                    'filename': filename,
                    'gtfs_path': gtfs_path,
                    'modified': modified,
                    'dates': dates
                })

    versions.sort(key=lambda v: (v['dates'][0], v['filename']), reverse=True)

    return versions


class Command(BaseCommand):
    def handle(self, *args, **options):
        command = TransXChangeCommand()
        command.undefined_holidays = set()
        command.notes = {}
        command.corrections = {}

        session = HTMLSession()

        sources = [source[0] for source in settings.PASSENGER_OPERATORS]

        for name, url, region_id, operators in settings.PASSENGER_OPERATORS:
            versions = get_versions(session, url)

            if not versions or not any(version['modified'] for version in versions):
                continue

            command.source, _ = DataSource.objects.get_or_create({'name': name}, url=url)
            command.source.datetime = timezone.now()
            command.operators = operators
            command.region_id = region_id
            command.service_descriptions = {}
            command.service_ids = set()
            command.route_ids = set()

            previous_date = None

            with transaction.atomic():

                for version in versions:  # newest first
                    print(version)

                    command.calendar_cache = {}
                    handle_file(command, version['filename'])

                    start_date = dateparse.parse_date(version['dates'][0])

                    routes = command.source.route_set.filter(code__startswith=version['filename'])
                    calendars = Calendar.objects.filter(trip__route__in=routes)
                    calendars.filter(start_date__lt=start_date).update(start_date=start_date)
                    routes.filter(start_date__lt=start_date).update(start_date=start_date)

                    if previous_date:  # if there is a newer dataset, set end date
                        new_end_date = previous_date - timedelta(days=1)
                        calendars.update(end_date=new_end_date)
                        routes.update(end_date=new_end_date)
                    previous_date = start_date

                    if version['dates'][0] <= str(command.source.datetime.date()):
                        break

                routes = Route.objects.filter(service__source=command.source)
                print('duplicate routes:', routes.exclude(source=command.source).delete())

                # delete route data from TNDS
                routes = Route.objects.filter(service__operator__in=operators.values())
                print('other source routes:', routes.exclude(source__name__in=sources).delete())

                services = Service.objects.filter(operator__in=operators.values(), current=True, route=None)
                print('other source services:', services.update(current=False))

                # delete route data from old versions
                routes = command.source.route_set
                for version in versions:
                    routes = routes.exclude(code__startswith=version['filename'])
                    if version['dates'][0] <= str(command.source.datetime.date()):
                        break
                print('old routes:', routes.delete())

                # mark old services as not current
                print('old services:', command.mark_old_services_as_not_current())

            for version in versions:
                handle_gtfs(list(operators.values()), version['gtfs_path'])

            command.source.save(update_fields=['datetime'])
        else:
            sleep(2)

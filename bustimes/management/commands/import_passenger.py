"""Import timetable data "fresh from the cow"
"""

import os
import requests
import zipfile
from urllib.parse import urljoin, urlparse
from time import sleep
from requests_html import HTMLSession
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q, OuterRef, Exists
from busstops.models import DataSource, Service, ServiceColour
from .import_bod import handle_file, get_operator_ids
from .import_transxchange import Command as TransXChangeCommand
from .import_gtfs import read_file
from ...utils import write_file
from ...models import Route


def handle_gtfs(operators, url):
    gtfs_dir = os.path.join(settings.DATA_DIR, 'gtfs')
    if not os.path.exists(gtfs_dir):
        os.mkdir(gtfs_dir)

    filename = os.path.basename(urlparse(url).path)
    path = os.path.join(gtfs_dir, filename)

    if os.path.exists(path):
        return

    response = requests.get(url, stream=True)
    write_file(path, response)

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
            )
            service.colour = colour
            service.save(update_fields=['colour'])


def get_version(url, element, heading):
    modified = False

    filename = os.path.basename(urlparse(url).path)
    path = os.path.join(settings.DATA_DIR, filename)

    if not os.path.exists(path):
        response = requests.get(url, stream=True)
        url = response.url  # in case there was a redirect
        filename = os.path.basename(urlparse(url).path)
        path = os.path.join(settings.DATA_DIR, filename)

        if not os.path.exists(path):
            write_file(path, response)
            modified = True

    if '(' in heading:
        heading = heading.split('(')[-1][:-1]
    dates = heading.split(' to ')

    return {
        'filename': filename,
        'modified': modified,
        'dates': dates
    }


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
            url = urljoin(element.base_url, element.attrs['href'])
            if '/txc' in url:
                versions.append(get_version(url, element, heading))
            elif '/gtfs' in url:
                versions[-1]['gtfs'] = url

    versions.sort(key=lambda v: (v['dates'][0], v['filename']), reverse=True)

    return versions


class Command(BaseCommand):
    @staticmethod
    def add_arguments(parser):
        parser.add_argument('operator', type=str, nargs='?')

    def handle(self, operator, *args, **options):
        command = TransXChangeCommand()
        command.set_up()

        session = HTMLSession()

        sources = DataSource.objects.filter(url__in=[values[1] for values in settings.PASSENGER_OPERATORS])

        for name, url, region_id, operators_dict in settings.PASSENGER_OPERATORS:
            if operator and operator != name:
                continue

            versions = get_versions(session, url)

            if versions:
                prefix = versions[0]['filename'].split('_')[0]
                prefix = f'{prefix}_'  # eg 'transdevblazefield_'
                for filename in os.listdir(settings.DATA_DIR):
                    if filename.startswith(prefix):
                        if not any(filename == version['filename'] for version in versions):
                            os.remove(os.path.join(settings.DATA_DIR, filename))
            else:
                sleep(2)
                continue

            new_versions = any(version['modified'] for version in versions)

            operators = operators_dict.values()

            command.source, _ = DataSource.objects.get_or_create({'name': name}, url=url)

            if new_versions:
                print(name)

                command.source.datetime = timezone.now()
                command.operators = operators_dict
                command.region_id = region_id
                command.service_ids = set()
                command.route_ids = set()
                command.garages = {}

                for version in versions:  # newest first
                    if version['modified']:
                        print(version)
                        handle_file(command, version['filename'])

                routes = Route.objects.filter(service__source=command.source)
                print('  duplicate routes:', routes.exclude(source=command.source).delete())

                # delete route data from TNDS
                routes = Route.objects.filter(service__operator__in=operators)
                print('  other source routes:', routes.exclude(source__in=sources).delete())

                services = Service.objects.filter(operator__in=operators, current=True, route=None)
                print('  other source services:', services.update(current=False))

                operator_ids = get_operator_ids(command.source)
                print('  ', operator_ids)

                foreign_operators = [o for o in operator_ids if o not in operators]
                print('  ', foreign_operators)

                if foreign_operators:
                    print(command.source.service_set.filter(
                        ~Exists(
                            Service.operator.through.objects.filter(
                                service=OuterRef('service')
                            ).filter(operator__in=operators)
                        ),
                    ).delete())

            # even if there are no new versions, delete old routes from expired versions
            old_routes = command.source.route_set
            for version in versions:
                old_routes = old_routes.filter(~Q(code__startswith=version['filename']))
            old_routes = old_routes.delete()
            if not new_versions:
                if old_routes[0]:
                    print(name)
                else:
                    sleep(2)
                    continue
            print('  old routes:', old_routes)

            # mark old services as not current
            old_services = command.source.service_set.filter(current=True, route=None)
            print('  old services:', old_services.update(current=False))

            if new_versions:
                command.finish_services()

                for version in versions:
                    if 'gtfs' in version:
                        handle_gtfs(list(operators), version['gtfs'])

                command.source.save(update_fields=['datetime'])

        command.debrief()

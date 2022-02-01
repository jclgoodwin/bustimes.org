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
from django.db.models import Q
from busstops.models import DataSource, Service, ServiceColour
from .import_bod import handle_file, get_operator_ids, clean_up, logger
from .import_transxchange import Command as TransXChangeCommand
from .import_gtfs import read_file
from ...utils import write_file


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


def get_version(url):
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

    return {
        'url': url,
        'filename': filename,
        'modified': modified,
    }


def get_versions(session, url):
    versions = []
    try:
        response = session.get(url, timeout=5)
    except requests.RequestException as e:
        logger.warning(f"{url} {e}")
        sleep(5)
        return
    if not response.ok:
        logger.warning(f"{url} {response}")
        sleep(5)
        return
    for element in response.html.find():
        if element.tag == 'a':
            url = urljoin(element.base_url, element.attrs['href'])
            if '/current' in url:
                if 'gtfs' not in url:
                    current = session.head(url).headers.get('location')
            elif '/txc' in url:
                versions.append(get_version(url))
            elif '/gtfs' in url:
                versions[-1]['gtfs'] = url

                if versions[-1]['url'] == current:  # stop - not interested in older data
                    break

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

            if new_versions or operator:
                logger.info(name)

                command.source.datetime = timezone.now()
                command.operators = operators_dict
                command.region_id = region_id
                command.service_ids = set()
                command.route_ids = set()
                command.garages = {}

                for version in versions:  # newest first
                    if version['modified'] or operator:
                        logger.info(version)
                        handle_file(command, version['filename'], qualify_filename=True)

                clean_up(operators, sources)

                operator_ids = get_operator_ids(command.source)
                logger.info(f"  {operator_ids}")

                foreign_operators = [o for o in operator_ids if o not in operators]
                logger.info(f"  {foreign_operators}")

            # even if there are no new versions, delete old routes from expired versions
            old_routes = command.source.route_set
            for version in versions:
                old_routes = old_routes.filter(~Q(code__startswith=version['filename']))
            old_routes = old_routes.delete()
            if not new_versions:
                if old_routes[0]:
                    logger.info(name)
                else:
                    sleep(2)
                    continue
            logger.info(f"  old routes: {old_routes}")

            # mark old services as not current
            old_services = command.source.service_set.filter(current=True, route=None)
            logger.info(f"  old services: {old_services.update(current=False)}")

            if new_versions or operator:
                command.finish_services()

                if name in ('Nottingham City Transport', 'Reading Buses', 'Transdev Blazefield', 'Cardiff Bus'):
                    # get colours from the GTFS data
                    for version in versions:
                        if 'gtfs' in version:
                            handle_gtfs(list(operators), version['gtfs'])
                            break

                command.source.save()

        command.debrief()

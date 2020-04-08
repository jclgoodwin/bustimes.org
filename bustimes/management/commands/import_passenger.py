"""Import timetable data "fresh from the cow"
"""

import os
import logging
import zipfile
import xml.etree.cElementTree as ET
from datetime import timedelta
from requests_html import HTMLSession
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone, dateparse
from busstops.models import DataSource, Service
from .import_gtfs import download_if_modified
from .import_transxchange import Command as TransXChangeCommand
from ...models import Route, Calendar


logger = logging.getLogger(__name__)


def handle_file(command, path):
    # the downloaded file might be plain XML, or a zipped archive - we just don't know yet
    try:
        with zipfile.ZipFile(os.path.join(settings.DATA_DIR, path)) as archive:
            for filename in archive.namelist():
                with archive.open(filename) as open_file:
                    try:
                        command.handle_file(open_file, os.path.join(path, filename))
                    except (ET.ParseError, ValueError) as e:
                        print(filename)
                        logger.error(e, exc_info=True)
    except zipfile.BadZipFile:
        with open(os.path.join(settings.DATA_DIR, path)) as open_file:
            command.handle_file(open_file, path)


class Command(BaseCommand):
    def handle(self, *args, **options):
        command = TransXChangeCommand()
        command.undefined_holidays = set()
        command.notes = {}
        command.corrections = {}

        session = HTMLSession()

        sources = [source[0] for source in settings.PASSENGER_OPERATORS]

        for name, url, region_id, operators in settings.PASSENGER_OPERATORS:

            command.source, _ = DataSource.objects.get_or_create({'url': url}, name=name)
            command.source.datetime = timezone.now()
            command.operators = operators
            command.region_id = region_id
            command.service_descriptions = {}
            command.service_codes = set()

            versions = []
            response = session.get(url)
            for element in response.html.find():
                if element.tag == 'h3':
                    heading = element.text
                elif element.tag == 'a':
                    url = element.attrs['href']
                    if '/txc/' in url:
                        url = element.attrs['href']
                        filename = url.split('/')[-1]
                        path = os.path.join(settings.DATA_DIR, filename)
                        modified = download_if_modified(path, url)
                        dates = heading.split(' to ')
                        versions.append(
                            (filename, modified, dates)
                        )

            versions.sort(key=lambda t: (t[2][0], t[0]), reverse=True)

            if any(modified for _, modified, _ in versions):
                previous_date = None

                for path, modified, dates in versions:  # newest first
                    print(path, modified, dates)

                    command.calendar_cache = {}
                    handle_file(command, path)

                    start_date = dateparse.parse_date(dates[0])

                    routes = command.source.route_set.filter(code__startswith=path)
                    calendars = Calendar.objects.filter(trip__route__in=routes)
                    print(calendars.filter(start_date__lt=start_date).update(start_date=start_date))
                    print(routes.filter(start_date__lt=start_date).update(start_date=start_date))

                    if previous_date:  # if there is a newer dataset, set end date
                        new_end_date = previous_date - timedelta(days=1)
                        print(calendars.update(end_date=new_end_date))
                        print(routes.update(end_date=new_end_date))
                    previous_date = start_date

                    if dates[0] <= str(command.source.datetime.date()):
                        break

                # delete route data from TNDS
                routes = Route.objects.filter(service__operator__in=operators.values())
                print(routes.exclude(source__name__in=sources).delete())

                services = Service.objects.filter(operator__in=operators.values(), current=True, route=None)
                print(services.filter(route=None).update(current=False))

                # mark old services as not current
                print(command.source.service_set.exclude(service_code__in=command.service_codes).update(current=False))

                # delete route data from old services
                print(command.source.route_set.filter(service__current=False).delete())

"""Import timetable data "fresh from the cow"
"""

import os
import logging
import zipfile
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
            command.calendar_cache = {}

            versions = []
            response = session.get(url)
            for element in response.html.find():
                if element.tag == 'h3':
                    heading = element.text
                elif element.tag == 'a':
                    url = element.attrs['href']
                    if '/txc/' in url:
                        url = element.attrs['href']
                        path = url.split('/')[-1]
                        modified = download_if_modified(path, url)
                        dates = heading.split(' to ')
                        versions.append(
                            (path, modified, dates)
                        )
                        if dates[0] <= str(command.source.datetime.date()):
                            break

            if any(modified for path, modified, dates in versions):
                previous_date = None

                for path, modified, dates in versions:  # newest first
                    print(path, modified, dates)

                    # the downloaded file might be plain XML, or a zipped archive - we just don't know yet
                    try:
                        with zipfile.ZipFile(path) as archive:
                            for filename in archive.namelist():
                                with archive.open(filename) as open_file:
                                    try:
                                        command.handle_file(open_file, os.path.join(path, filename))
                                    except ValueError as e:
                                        logger.error(e, exc_info=True)
                    except zipfile.BadZipFile:
                        with open(path) as open_file:
                            command.handle_file(open_file, path)
                    start_date = dateparse.parse_date(dates[0])

                    routes = command.source.route_set.filter(code__startswith=path)
                    print(routes.filter(start_date__lt=start_date).update(start_date=start_date))

                    if previous_date:  # if there is a newer dataset, set end date
                        new_end_date = previous_date - timedelta(days=1)
                        print(Calendar.objects.filter(trip__route__in=routes).update(end_date=new_end_date))
                        print(routes.update(end_date=new_end_date))
                    previous_date = start_date

                # delete route data from TNDS
                routes = Route.objects.filter(service__operator__in=operators.values())
                print(routes.exclude(source__name__in=sources).delete())

                services = Service.objects.filter(operator__in=operators.values(), current=True, route=None)
                print(services.filter(route=None).update(current=False))

                # mark old services as not current
                print(command.source.service_set.exclude(service_code__in=command.service_codes).update(current=False))

                # delete route data from old services
                print(command.source.route_set.filter(service__current=False).delete())

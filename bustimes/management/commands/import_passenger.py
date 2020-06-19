"""Import timetable data "fresh from the cow"
"""

import os
import requests
from time import sleep
from datetime import timedelta
from requests_html import HTMLSession
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone, dateparse
from busstops.models import DataSource, Service
from .import_bod import handle_file
from .import_transxchange import Command as TransXChangeCommand
from ...utils import write_file
from ...models import Route, Calendar


def download_if_new(path, url):
    if not os.path.exists(path):
        response = requests.get(url, stream=True)
        write_file(path, response)
        return True
    return False


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
            command.service_ids = set()

            versions = []
            try:
                response = session.get(url, timeout=5)
            except requests.RequestException as e:
                print(url, e)
                sleep(5)
                continue
            if not response.ok:
                print(url, response)
                sleep(5)
                continue
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
                        dates = heading.split(' to ')
                        versions.append(
                            (filename, modified, dates)
                        )

            versions.sort(key=lambda t: (t[2][0], t[0]), reverse=True)

            if any(modified for _, modified, _ in versions):
                previous_date = None

                with transaction.atomic():

                    for path, modified, dates in versions:  # newest first
                        print(path, modified, dates)

                        command.calendar_cache = {}
                        handle_file(command, path)

                        start_date = dateparse.parse_date(dates[0])

                        routes = command.source.route_set.filter(code__startswith=path)
                        calendars = Calendar.objects.filter(trip__route__in=routes)
                        calendars.filter(start_date__lt=start_date).update(start_date=start_date)
                        routes.filter(start_date__lt=start_date).update(start_date=start_date)

                        if previous_date:  # if there is a newer dataset, set end date
                            new_end_date = previous_date - timedelta(days=1)
                            calendars.update(end_date=new_end_date)
                            routes.update(end_date=new_end_date)
                        previous_date = start_date

                        if dates[0] <= str(command.source.datetime.date()):
                            break

                    # delete route data from TNDS
                    routes = Route.objects.filter(service__operator__in=operators.values())
                    print('other source routes:', routes.exclude(source__name__in=sources).delete())

                    services = Service.objects.filter(operator__in=operators.values(), current=True, route=None)
                    print('other source services:', services.update(current=False))

                    # delete route data from old versions
                    routes = command.source.route_set
                    for prefix, _, dates in versions:
                        routes = routes.exclude(code__startswith=prefix)
                        if dates[0] <= str(command.source.datetime.date()):
                            break
                    print('old routes:', routes.delete())

                    # mark old services as not current
                    print('old services:',
                          command.source.service_set.filter(current=True, route=None).update(current=False))
            else:
                sleep(5)

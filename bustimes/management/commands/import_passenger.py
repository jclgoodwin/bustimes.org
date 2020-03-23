"""Import timetable data "fresh from the cow"
"""

import logging
from requests_html import HTMLSession
from django.core.management.base import BaseCommand
from busstops.models import DataSource
from .import_gtfs import download_if_modified
from .import_transxchange import Command as TransXChangeCommand


logger = logging.getLogger(__name__)


sources = (
    ('Borders Buses', 'https://www.bordersbuses.co.uk/open-data', 'S'),
    ('Reading Buses', 'https://www.reading-buses.co.uk/open-data', 'SE'),
)


class Command(BaseCommand):
    def handle(self, *args, **options):

        session = HTMLSession()
        command = TransXChangeCommand()

        for name, url, region_id in sources:
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
                        print(url, heading, modified)

                        command.source, _ = DataSource.objects.get_or_create({'url': url}, name=name)
                        command.calendar_cache = {}
                        command.undefined_holidays = set()
                        command.notes = {}
                        command.region_id = region_id
                        command.service_descriptions = {}
                        command.service_codes = set()
                        command.corrections = {}
                        with open(path) as open_file:
                            command.handle_file(open_file, path)

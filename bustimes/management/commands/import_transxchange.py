"""
Usage:

    ./manage.py import_transxchange EA.zip [EM.zip etc]
"""

import zipfile
from django.core.management.base import BaseCommand
from ...models import Source, Route, Calendar, CalendarDate, Trip, StopTime
from timetables.txc import TransXChange


NS = {'txc': 'http://www.transxchange.org.uk/'}


def get_line_name_and_brand(service_element):
    line_name = service_element.find('txc:Lines', NS)[0][0].text
    if '|' in line_name:
        line_name, line_brand = line_name.split('|', 1)
    else:
        line_brand = ''
    return line_name, line_brand


class Command(BaseCommand):
    @staticmethod
    def add_arguments(parser):
        parser.add_argument('filenames', nargs='+', type=str)

    def handle(self, *args, **options):
        for archive_name in options['filenames']:
            self.handle_archive(archive_name)

    def handle_archive(self, archive_name):
        source, source_created = Source.objects.get_or_create(name=archive_name)
        if not source_created:
            source.route_set.all().delete()
        with zipfile.ZipFile(archive_name) as archive:
            for filename in archive.namelist():
                if filename.endswith('.xml'):
                    with archive.open(filename) as open_file:
                        self.handle_file(open_file, filename, source)

    def handle_file(self, open_file, filename, source):
        transxchange = TransXChange(open_file)

        service_element = transxchange.element.find('txc:Services/txc:Service', NS)
        line_name, line_brand = get_line_name_and_brand(service_element)

        route, created = Route.objects.get_or_create(
            {'line_name': line_name, 'line_brand': line_brand, 'start_date': transxchange.operating_period.start,
             'end_date': transxchange.operating_period.end}, source=source, code=filename
        )

        calendar_dates = []
        stop_times = []

        for journey in transxchange.journeys:
            calendar = Calendar(
                mon=False,
                tue=False,
                wed=False,
                thu=False,
                fri=False,
                sat=False,
                sun=False,
                start_date=transxchange.operating_period.start,
                end_date=transxchange.operating_period.end
            )

            for day in journey.operating_profile.regular_days:
                if day == 0:
                    calendar.mon = True
                elif day == 1:
                    calendar.tue = True
                elif day == 2:
                    calendar.wed = True
                elif day == 3:
                    calendar.thu = True
                elif day == 4:
                    calendar.fri = True
                elif day == 5:
                    calendar.sat = True
                elif day == 6:
                    calendar.sun = True
            calendar.save()

            calendar_dates += [
                CalendarDate(start_date=date_range.start, end_date=date_range.end, calendar=calendar, operation=False)
                for date_range in journey.operating_profile.nonoperation_days
            ]
            calendar_dates += [
                CalendarDate(start_date=date_range.start, end_date=date_range.end, calendar=calendar, operation=True)
                for date_range in journey.operating_profile.operation_days
            ]

            trip = Trip(
                inbound=journey.journey_pattern.direction == 'inbound',
                calendar=calendar,
                route=route,
                journey_pattern=journey.journey_pattern.id,
            )
            trip.save()

            stop_times += [
                StopTime(
                    stop_code=cell.stopusage.stop.atco_code,
                    trip=trip,
                    arrival=cell.arrival_time,
                    departure=cell.departure_time,
                    sequence=i
                ) for i, cell in enumerate(journey.get_times())
            ]

        CalendarDate.objects.bulk_create(calendar_dates)
        StopTime.objects.bulk_create(stop_times)

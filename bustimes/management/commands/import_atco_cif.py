# import logging
# import warnings
# import os
# import shutil
# import csv
# import yaml
import zipfile
# import xml.etree.cElementTree as ET
from datetime import date, timedelta
# from django.conf import settings
from django.core.management.base import BaseCommand
# from django.db import transaction
# from django.contrib.gis.geos import LineString, MultiLineString
from django.utils import timezone
from busstops.models import Service, DataSource
from ...models import Route, Calendar, Trip, StopTime, Note
# from timetables.txc import TransXChange, Grouping, sanitize_description_part


# logger = logging.getLogger(__name__)


def parse_date(string):
    if string == b'99999999':
        return
    return date(year=int(string[:4]), month=int(string[4:6]), day=int(string[6:]))


def parse_time(string):
    return timedelta(hours=int(string[:2]), minutes=int(string[2:]))


class Command(BaseCommand):
    @staticmethod
    def add_arguments(parser):
        parser.add_argument('filenames', nargs='+', type=str)

    def handle(self, *args, **options):
        for archive_name in options['filenames']:
            self.handle_archive(archive_name)

    def handle_archive(self, archive_name):
        self.route = None
        self.trip = None
        self.routes = {}
        self.calendars = {}
        self.stop_times = []
        self.notes = []
        if 'ulb' in archive_name.lower():
            source_name = 'ULB'
        else:
            source_name = 'MET'
        self.source, source_created = DataSource.objects.get_or_create(name=source_name)
        self.source.route_set.all().delete()
        self.source.datetime = timezone.localtime()

        with zipfile.ZipFile(archive_name) as archive:
            for filename in archive.namelist():
                if filename.endswith('.cif'):
                    with archive.open(filename) as open_file:
                        self.handle_file(open_file)

        StopTime.objects.bulk_create(self.stop_times)

        self.source.save(update_fields=['datetime'])

    def handle_file(self, open_file):
        # print(open_file)
        previous_line = None
        for line in open_file:
            self.handle_line(line, previous_line)
            previous_line = line

    def get_calendar(self, line):
        key = line[13:38]
        if key in self.calendars:
            return self.calendars[key]
        calendar = Calendar.objects.create(
            mon=line[29:30] == b'1',
            tue=line[30:31] == b'1',
            wed=line[31:32] == b'1',
            thu=line[32:33] == b'1',
            fri=line[33:34] == b'1',
            sat=line[34:35] == b'1',
            sun=line[35:36] == b'1',
            start_date=parse_date(line[13:21]),
            end_date=parse_date(line[21:29])
        )
        self.calendars[key] = calendar
        return calendar

    def handle_line(self, line, previous_line):
        identity = line[:2]

        if identity == b'QD':
            operator = line[3:7].decode().strip()
            line_name = line[7:11].decode().strip()
            key = f'{line_name}_{operator}'
            if key in self.routes:
                self.route = self.routes[key]
            else:
                description = line[12:].decode().strip()
                service, _ = Service.objects.update_or_create(
                    {
                        'line_name': line_name,
                        'description': description,
                        'date': self.source.datetime.date(),
                        'current': True,
                        'show_timetable': True,
                        'source': self.source,
                        'region_id': 'NI'
                    }, service_code=key
                )
                if operator:
                    service.operator.add(operator)
                self.route, _ = Route.objects.update_or_create(
                    code=key,
                    service=service,
                    line_name=line_name,
                    description=description,
                    source=self.source
                )
                self.routes[key] = self.route

        elif identity == b'QS':
            self.sequence = 0
            if self.route:
                calendar = self.get_calendar(line)
                self.trip = Trip(
                    route=self.route,
                    calendar=calendar,
                    inbound=line[64:65] == b'I'
                )

        elif identity == b'QO':
            if self.trip:
                departure = parse_time(line[14:18]),
                self.stop_times.append(
                    StopTime(
                        arrival=departure,
                        departure=departure,
                        stop_code=line[2:14].decode(),
                        sequence=0,
                        trip=self.trip
                    )
                )
                self.trip.start = departure

        elif identity == b'QI':
            if self.trip:
                self.sequence += 1
                timing_status = line[26:28]
                if timing_status == b'T1':
                    timing_status = 'PTP'
                else:
                    assert timing_status == b'T0'
                    timing_status = 'OTH'
                self.stop_times.append(
                    StopTime(
                        arrival=parse_time(line[14:18]),
                        departure=parse_time(line[18:22]),
                        stop_code=line[2:14].decode(),
                        sequence=self.sequence,
                        trip=self.trip,
                        timing_status=timing_status
                    )
                )

        elif identity == b'QT':
            if self.trip:
                arrival = parse_time(line[14:18])
                self.sequence += 1
                stop_code = line[2:14].decode()
                self.stop_times.append(
                    StopTime(
                        arrival=arrival,
                        departure=arrival,
                        stop_code=stop_code,
                        sequence=self.sequence,
                        trip=self.trip
                    )
                )
                self.trip.destination_id = stop_code
                self.trip.end = arrival

                self.trip.save()

                self.trip.notes.set(self.notes)
                self.notes = []

                for stop_time in self.stop_times:
                    stop_time.trip = stop_time.trip  # set trip_id
                StopTime.objects.bulk_create(self.stop_times)
                self.stop_times = []

        elif identity == b'QN':
            if previous_line[:2] == b'QI':
                note = line[7:].decode().strip().lower()
                if note == 'pick up only' or note == 'pick up  only':
                    self.stop_times[-1].activity = 'pickUp'
                elif note == 'set down only' or note == '.set down only':
                    self.stop_times[-1].activity = 'setDown'
                else:
                    print(note)
            elif previous_line[:2] == b'QS':
                code = line[2:7].decode().strip()
                note = line[7:].decode().strip()
                note, _ = Note.objects.get_or_create(code=code, text=note)
                self.notes.append(note)
            else:
                print(previous_line[:2], line)

        # # QI - Journey Intermediate
        # # QT - Journey Destination
        # elif record_identity in ('QO', 'QI', 'QT'):
        #     cls.handle_stop(line)
        # elif record_identity == 'QL':
        #     cls.handle_location(line)
        # elif record_identity == 'QB':
        #     cls.handle_location_additional(line)

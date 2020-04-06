"""
Usage:

    ./manage.py import_transxchange EA.zip [EM.zip etc]
"""

import logging
import warnings
import os
import csv
import yaml
import zipfile
import xml.etree.cElementTree as ET
from django.conf import settings
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import LineString, MultiLineString
from django.db import transaction
from django.utils import timezone
from busstops.models import (Operator, Service, DataSource, StopPoint, StopUsage, ServiceCode)
from ...models import Route, Calendar, CalendarDate, Trip, StopTime, Note
from timetables.txc import TransXChange, Grouping, sanitize_description_part


logger = logging.getLogger(__name__)


NS = {'txc': 'http://www.transxchange.org.uk/'}
BANK_HOLIDAYS = {
    'ChristmasDay': '2019-12-25',
    'BoxingDay':  '2019-12-26',
    'NewYearsDay':  '2020-01-01',
    'AllBankHolidays': '2020-01-01',
    'GoodFriday': '2020-04-10',
    'EasterMonday': '2020-04-13',
}


def sanitize_description(name):
    """
    Given an oddly formatted description from the North East,
    like 'Bus Station bay 5,Blyth - Grange Road turning circle,Widdrington Station',
    returns a shorter, more normal version like
    'Blyth - Widdrington Station'
    """

    parts = [sanitize_description_part(part) for part in name.split(' - ')]
    return ' - '.join(parts)


def get_line_name_and_brand(service_element):
    line_name = service_element.find('txc:Lines', NS)[0][0].text
    if '|' in line_name:
        line_name, line_brand = line_name.split('|', 1)
    else:
        line_brand = ''
    return line_name, line_brand


def get_service_code(filename):
    """
    Given a filename like 'ea_21-45A-_-y08-1.xml',
    returns a service_code like 'ea_21-45A-_-y08'
    """
    parts = filename.split('-')  # ['ea_21', '3', '_', '1']
    if len(parts) == 5:
        net = parts[0].split('_')[0]
        if len(net) <= 3 and net.islower():
            return '-'.join(parts[:-1])


def get_operator_code(operator_element, element_name):
    element = operator_element.find('txc:{}'.format(element_name), NS)
    if element is not None:
        return element.text


def get_operator_name(operator_element):
    "Given an Operator element, returns the operator name or None"

    for element_name in ('TradingName', 'OperatorNameOnLicence', 'OperatorShortName'):
        name = get_operator_code(operator_element, element_name)
        if name:
            return name.replace('&amp;', '&')


def get_operator_by(scheme, code):
    if code:
        return Operator.objects.filter(operatorcode__code=code, operatorcode__source__name=scheme).first()


def line_string_from_journeypattern(journeypattern, stops):
    points = []
    stop = stops.get(journeypattern.sections[0].timinglinks[0].origin.stop.atco_code)
    if stop and stop.latlong:
        points.append(stop.latlong)
    for timinglink in journeypattern.get_timinglinks():
        stop = stops.get(timinglink.destination.stop.atco_code)
        if stop and stop.latlong:
            points.append(stop.latlong)
    try:
        linestring = LineString(points)
        return linestring
    except ValueError:
        pass


class Command(BaseCommand):
    @staticmethod
    def add_arguments(parser):
        parser.add_argument('archives', nargs=1, type=str)
        parser.add_argument('files', nargs='*', type=str)

    def handle(self, *args, **options):
        self.calendar_cache = {}
        self.undefined_holidays = set()
        self.notes = {}
        open_data_operators = []
        for _, _, operators in settings.BOD_OPERATORS:
            open_data_operators += operators.values()
        for _, _, _, operators in settings.PASSENGER_OPERATORS:
            open_data_operators += operators.values()
        self.open_data_operators = set(open_data_operators)
        for archive_name in options['archives']:
            self.handle_archive(archive_name, options['files'])
        if self.undefined_holidays:
            print(self.undefined_holidays)

    def set_region(self, archive_name):
        self.region_id, _ = os.path.splitext(os.path.basename(archive_name))

        self.source, created = DataSource.objects.get_or_create(name=self.region_id)

        if self.region_id == 'NCSD':
            self.region_id = 'GB'
        elif self.region_id == 'IOM':
            self.region_id = 'IM'

    def get_operator(self, operator_element):
        "Given an Operator element, returns an operator code for an operator that exists."

        for tag_name, scheme in (
            ('NationalOperatorCode', 'National Operator Codes'),
            ('LicenceNumber', 'Licence'),
        ):
            operator_code = get_operator_code(operator_element, tag_name)
            if operator_code:
                operator = get_operator_by(scheme, operator_code)
                if operator:
                    return operator

        # Get by regional operator code
        operator_code = get_operator_code(operator_element, 'OperatorCode')
        if operator_code:
            if len(self.source.name) > 4:  # not a TNDS source
                operator_code = self.operators.get(operator_code, operator_code)
            operator = get_operator_by(self.region_id, operator_code)
            if not operator:
                operator = get_operator_by('National Operator Codes', operator_code)
            if operator:
                return operator

        name = get_operator_name(operator_element)

        if name == 'Bus Vannin':
            return Operator.objects.get(name=name)

        if name not in {'Replacement Service', 'UNKWN'}:
            warnings.warn('Operator not found:\n{}'.format(ET.tostring(operator_element).decode()))

    def get_operators(self, transxchange, service):
        operators = transxchange.operators
        if len(operators) > 1:
            journey_operators = {journey.operator for journey in transxchange.journeys}
            journey_operators.add(service.operator)
            operators = [operator for operator in operators if operator.get('id') in journey_operators]
        operators = (self.get_operator(operator) for operator in operators)
        return [operator for operator in operators if operator]

    def set_service_descriptions(self, archive):
        # the NCSD has service descriptions in a separate file:
        self.service_descriptions = {}
        if 'IncludedServices.csv' in archive.namelist():
            with archive.open('IncludedServices.csv') as csv_file:
                reader = csv.DictReader(line.decode('utf-8') for line in csv_file)
                # e.g. {'NATX323': 'Cardiff - Liverpool'}
                for row in reader:
                    key = f"{row['Operator']}{row['LineName']}{row['Dir']}"
                    self.service_descriptions[key] = row['Description']

    def get_service_descriptions(self, filename):
        parts = filename.split('_')
        operator = parts[-2]
        line_name = parts[-1][:-4]
        key = f'{operator}{line_name}'
        outbound = self.service_descriptions.get(f'{key}O', '')
        inbound = self.service_descriptions.get(f'{key}I', '')
        return outbound, inbound

    def handle_archive(self, archive_name, filenames):
        self.service_codes = set()

        self.set_region(archive_name)

        self.source.datetime = timezone.now()

        with open(os.path.join(settings.DATA_DIR, 'services.yaml')) as open_file:
            self.corrections = yaml.load(open_file, Loader=yaml.FullLoader)

        with zipfile.ZipFile(archive_name) as archive:

            self.set_service_descriptions(archive)

            for filename in filenames or archive.namelist():
                if filename.endswith('.xml'):
                    with archive.open(filename) as open_file:
                        with transaction.atomic():
                            self.handle_file(open_file, filename)

        old_services = self.source.service_set.filter(current=True).exclude(service_code__in=self.service_codes)
        old_services.update(current=False)

        self.source.save(update_fields=['datetime'])

        StopPoint.objects.filter(active=False, service__current=True).update(active=True)
        StopPoint.objects.filter(active=True, service__isnull=True).update(active=False)
        self.source.route_set.filter(service__current=False).delete()
        Service.objects.filter(region=self.region_id, current=False, geometry__isnull=False).update(geometry=None)

    def get_calendar(self, operating_profile, operating_period):
        calendar_dates = [
            CalendarDate(start_date=date_range.start, end_date=date_range.end, dates=date_range.dates(), special=True,
                         operation=False) for date_range in operating_profile.nonoperation_days
        ]
        calendar_dates += [
            CalendarDate(start_date=date_range.start, end_date=date_range.end, dates=date_range.dates(), special=True,
                         operation=True) for date_range in operating_profile.operation_days
        ]

        for holiday in operating_profile.operation_bank_holidays:
            if holiday in BANK_HOLIDAYS:
                calendar_dates.append(
                    CalendarDate(start_date=BANK_HOLIDAYS[holiday], end_date=BANK_HOLIDAYS[holiday],
                                 dates=(BANK_HOLIDAYS[holiday], BANK_HOLIDAYS[holiday]), special=True, operation=True)
                )
            else:
                self.undefined_holidays.add(holiday)
        for holiday in operating_profile.nonoperation_bank_holidays:
            if holiday in BANK_HOLIDAYS:
                calendar_dates.append(
                    CalendarDate(start_date=BANK_HOLIDAYS[holiday], end_date=BANK_HOLIDAYS[holiday],
                                 dates=(BANK_HOLIDAYS[holiday], BANK_HOLIDAYS[holiday]), special=True, operation=False)
                )
            else:
                self.undefined_holidays.add(holiday)

        if operating_profile.servicedorganisation:
            org = operating_profile.servicedorganisation

            nonoperation_days = (org.nonoperation_workingdays and org.nonoperation_workingdays.working_days or
                                 org.nonoperation_holidays and org.nonoperation_holidays.holidays)
            if nonoperation_days:
                calendar_dates += [
                    CalendarDate(start_date=date_range.start, end_date=date_range.end, dates=date_range.dates(),
                                 operation=False)
                    for date_range in nonoperation_days
                ]

            operation_days = (org.operation_workingdays and org.operation_workingdays.working_days or
                              org.operation_holidays and org.operation_holidays.holidays)
            if operation_days:
                calendar_dates += [
                    CalendarDate(start_date=date_range.start, end_date=date_range.end, dates=date_range.dates(),
                                 operation=True)
                    for date_range in operation_days
                ]

        calendar_dates = [dates for dates in calendar_dates if not dates.end_date or dates.end_date >= dates.start_date]

        if not calendar_dates and not operating_profile.regular_days:
            return

        calendar_hash = f'{operating_profile.regular_days}{operating_period.dates()}'
        calendar_hash += ''.join(f'{date.dates}{date.operation}{date.special}' for date in calendar_dates)

        if calendar_hash in self.calendar_cache:
            return self.calendar_cache[calendar_hash]

        calendar = Calendar(
            mon=False,
            tue=False,
            wed=False,
            thu=False,
            fri=False,
            sat=False,
            sun=False,
            start_date=operating_period.start,
            end_date=operating_period.end,
            dates=operating_period.dates()
        )

        for day in operating_profile.regular_days:
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
        for date in calendar_dates:
            date.calendar = calendar
        CalendarDate.objects.bulk_create(calendar_dates)

        self.calendar_cache[calendar_hash] = calendar

        return calendar

    def handle_journeys(self, route, stops, transxchange, service):
        default_calendar = None

        for journey in transxchange.journeys:
            if journey.service_ref != service.service_code:
                continue

            calendar = None
            if journey.operating_profile:
                calendar = self.get_calendar(journey.operating_profile, service.operating_period)
            else:
                if not default_calendar:
                    default_calendar = self.get_calendar(service.operating_profile, service.operating_period)
                calendar = default_calendar

            if not calendar:
                continue

            trip = Trip(
                inbound=journey.journey_pattern.direction == 'inbound',
                calendar=calendar,
                route=route,
                journey_pattern=journey.journey_pattern.id,
            )

            stop_times = []
            for i, cell in enumerate(journey.get_times()):
                timing_status = cell.stopusage.timingstatus
                if timing_status == 'otherPoint':
                    timing_status = 'OTH'
                elif timing_status == 'principleTimingPoint':
                    timing_status = 'PTP'
                stop_time = StopTime(
                    stop_code=cell.stopusage.stop.atco_code,
                    trip=trip,
                    arrival=cell.arrival_time,
                    departure=cell.departure_time,
                    sequence=i,
                    timing_status=timing_status,
                    activity=cell.stopusage.activity or ''
                )
                if i == 0:
                    trip.start = stop_time.arrival or stop_time.departure
                if stop_time.stop_code in stops:
                    stop_time.stop_id = stop_time.stop_code
                    trip.destination_id = stop_time.stop_code
                stop_times.append(stop_time)
            if not trip.destination_id:
                print(stop_times)
                continue
            trip.end = stop_time.departure or stop_time.arrival
            trip.save()

            for note in journey.notes:
                note_cache_key = f'{note}:{journey.notes[note]}'
                if note_cache_key in self.notes:
                    note = self.notes[note_cache_key]
                else:
                    note, _ = Note.objects.get_or_create(code=note, text=journey.notes[note])
                    self.notes[note_cache_key] = note
                trip.notes.add(note)

            for stop_time in stop_times:
                stop_time.trip = stop_time.trip  # set trip_id
            StopTime.objects.bulk_create(stop_times)

    def handle_file(self, open_file, filename):
        transxchange = TransXChange(open_file)

        today = self.source.datetime.date()

        # stops:
        stops = StopPoint.objects.in_bulk(transxchange.stops.keys())
        stops_to_create = {atco_code: StopPoint(atco_code=atco_code, common_name=str(stop)[:48], active=True)
                           for atco_code, stop in transxchange.stops.items() if atco_code not in stops}
        if stops_to_create:
            StopPoint.objects.bulk_create(stops_to_create.values())
            stops = {**stops, **stops_to_create}

        for txc_service in transxchange.services.values():
            # if service.mode == 'underground':
            #     continue

            if txc_service.operating_period.end and txc_service.operating_period.end < today:
                continue

            service_code = get_service_code(filename)
            if service_code is None:
                service_code = txc_service.service_code

            line_name, line_brand = get_line_name_and_brand(txc_service.element)

            operators = self.get_operators(transxchange, txc_service)

            if len(self.source.name) <= 4:  # TNDS
                if operators and all(operator.id in self.open_data_operators for operator in operators):
                    continue
            else:  # not a TNDS source (slightly dodgy heuristic)
                try:
                    services = Service.objects.filter(operator__in=self.operators.values(), line_name__iexact=line_name)
                    services = services.defer('geometry')
                    try:
                        existing = services.get(current=True)
                    except Service.DoesNotExist:
                        existing = services.get()
                    service_code = existing.service_code
                    if not line_brand:
                        line_brand = existing.line_brand
                    if not txc_service.mode:
                        txc_service.mode = existing.mode

                except (Service.DoesNotExist, Service.MultipleObjectsReturned):
                    service_code = f'{self.source.id}-{service_code}'

            defaults = {
                'line_name': line_name,
                'line_brand': line_brand,
                'mode': txc_service.mode,
                'region_id': self.region_id,
                'date': today,
                'current': True,
                'source': self.source,
                'show_timetable': True
            }
            description = txc_service.description
            if not description or 'covid-19 timetable' in description.lower():
                description = f'{txc_service.origin} - {txc_service.destination}'
                if txc_service.vias:
                    description = f"{description} via {', '.join(txc_service.vias)}"
                print(description)
            if description:
                if self.region_id == 'NE':
                    description = sanitize_description(description)
                defaults['description'] = description

            groupings = {
                'outbound': Grouping('outbound', txc_service),
                'inbound': Grouping('inbound', txc_service)
            }

            for journey_pattern in txc_service.journey_patterns.values():
                if journey_pattern.direction == 'inbound':
                    grouping = groupings['inbound']
                else:
                    grouping = groupings['outbound']
                grouping.add_journey_pattern(journey_pattern)

            try:
                stop_usages = []
                for grouping in groupings.values():
                    if grouping.rows:
                        for i, row in enumerate(grouping.rows):
                            if row.part.stop.atco_code in stops:
                                timing_status = row.part.timingstatus
                                if timing_status == 'otherPoint':
                                    timing_status = 'OTH'
                                elif timing_status == 'principleTimingPoint':
                                    timing_status = 'PTP'
                                stop_usages.append(
                                    StopUsage(
                                        service_id=service_code,
                                        stop_id=row.part.stop.atco_code,
                                        direction=grouping.direction,
                                        order=i,
                                        timing_status=timing_status
                                    )
                                )
                        if grouping.direction == 'outbound' or grouping.direction == 'inbound':
                            # grouping.description_parts = transxchange.description_parts
                            defaults[grouping.direction + '_description'] = str(grouping)

                    line_strings = []
                    for pattern in txc_service.journey_patterns.values():
                        line_string = line_string_from_journeypattern(pattern, stops)
                        if line_string not in line_strings:
                            line_strings.append(line_string)
                multi_line_string = MultiLineString(*(ls for ls in line_strings if ls))

            except (AttributeError, IndexError) as error:
                logger.error(error, exc_info=True)
                defaults['show_timetable'] = False
                stop_usages = [StopUsage(service_id=service_code, stop_id=stop, order=0) for stop in stops]
                multi_line_string = None

            defaults['geometry'] = multi_line_string

            if self.service_descriptions:
                defaults['outbound_description'], defaults['inbound_description'] = self.get_service_descriptions(
                    filename)
                defaults['description'] = defaults['outbound_description'] or defaults['inbound_description']

            service, service_created = Service.objects.update_or_create(service_code=service_code, defaults=defaults)

            if service_created:
                service.operator.add(*operators)
                self.service_codes.add(service_code)
            else:
                if service.slug == service_code.lower():
                    service.slug = ''
                    service.save(update_fields=['slug'])
                service.operator.set(operators)
                if service_code not in self.service_codes:
                    self.service_codes.add(service_code)
                    self.source.route_set.filter(service=service_code).delete()
                    service.stops.clear()
            StopUsage.objects.bulk_create(stop_usages)

            # a code used in Traveline Cymru URLs:
            if self.source.name == 'W':
                if transxchange.journeys and transxchange.journeys[0].private_code:
                    private_code = transxchange.journeys[0].private_code
                    if ':' in private_code:
                        ServiceCode.objects.update_or_create({
                            'code': private_code.split(':', 1)[0]
                        }, service=service, scheme='Traveline Cymru')

            # timetable data:

            route_defaults = {
                'line_name': line_name,
                'line_brand': line_brand,
                'start_date': txc_service.operating_period.start,
                'end_date': txc_service.operating_period.end,
                'dates': txc_service.operating_period.dates(),
                'service': service,
            }
            if 'description' in defaults:
                route_defaults['description'] = defaults['description']

            route_code = filename
            if len(transxchange.services) > 1:
                route_code = f'{route_code}#{service_code}'

            route, route_created = Route.objects.get_or_create(route_defaults, source=self.source, code=route_code)

            self.handle_journeys(route, stops, transxchange, txc_service)

            if service_code in self.corrections:
                corrections = {}
                for field in self.corrections[service_code]:
                    if field == 'operator':
                        service.operator.set(self.corrections[service_code][field])
                    else:
                        corrections[field] = self.corrections[service_code][field]
                Service.objects.filter(service_code=service_code).update(**corrections)

            if service_code == 'twm_5-501-A-y11':  # Lakeside Coaches
                Trip.objects.filter(route__service=service_code, start='15:05').delete()
                Trip.objects.filter(route__service=service_code, start='15:30').delete()

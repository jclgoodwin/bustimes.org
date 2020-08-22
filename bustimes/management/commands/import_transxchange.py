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
from psycopg2.extras import DateRange
from titlecase import titlecase
from datetime import date
from django.conf import settings
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import LineString, MultiLineString
from django.db import transaction, IntegrityError, DataError
from django.utils import timezone
from busstops.models import Operator, Service, DataSource, StopPoint, StopUsage, ServiceCode, ServiceLink
from ...models import Route, Calendar, CalendarDate, Trip, StopTime, Note
from ...timetables import get_stop_usages
from timetables.txc import TransXChange, sanitize_description_part, Grouping


logger = logging.getLogger(__name__)


NS = {'txc': 'http://www.transxchange.org.uk/'}
"""
_________________________________________________________________________________________________
| AllBankHolidays | AllHolidaysExceptChristmas | Holidays             | NewYearsDay              |
|                 |                            |                      | 🏴󠁧󠁢󠁳󠁣󠁴󠁿 Jan2ndScotland        |
|                 |                            |                      | GoodFriday               |
|                 |                            |                      | 🏴󠁧󠁢󠁳󠁣󠁴󠁿 StAndrewsDay          |
|                 |                            |______________________|__________________________|
|                 |                            | HolidayMondays       | EasterMonday             |
|                 |                            |                      | MayDay                   |
|                 |                            |                      | SpringBank               |________
|                 |                            |                      | LateSummerBankHolidayNotScotland  |
|                 |                            |                      | AugustBankHolidayScotland   ______|
|                 |____________________________|______________________|____________________________|
|                 | Christmas            | ChristmasDay               |
|                 |                      | BoxingDay                  |
|                 |______________________|____________________________|
|                 | DisplacementHolidays | ChristmasDayHoliday        |
|                 |                      | BoxingDayHoliday           |
|                 |                      | NewYearsDayHoliday         |
|                 |                      | 🏴󠁧󠁢󠁳󠁣󠁴󠁿 Jan2ndScotlandHoliday   |
|                 |                      | 🏴󠁧󠁢󠁳󠁣󠁴󠁿 StAndrewsDayHoliday     |
|_________________|______________________|____________________________|
| EarlyRunOff     | ChristmasEve |
|                 | NewYearsEve  |
|_________________|______________|
"""

BANK_HOLIDAYS = {
    'AllBankHolidays': date(2020, 8, 31),
    'HolidayMondays': date(2020, 8, 31),
    'LateSummerBankHolidayNotScotland': date(2020, 8, 31),
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


def get_lines(service_element):
    lines = []
    for line_element in service_element.find('txc:Lines', NS):
        line_id = line_element.attrib['id']
        line_name = (line_element.find('txc:LineName', NS).text or '').strip()
        if '|' in line_name:
            line_name, line_brand = line_name.split('|', 1)
        else:
            line_brand = ''
        lines.append((line_id, line_name, line_brand))
    return lines


def get_service_code(filename):
    """
    Given a filename like 'ea_21-45A-_-y08-1.xml',
    returns a service_code like 'ea_21-45A-_-y08'
    """
    parts = filename.split('-')  # ['ea_21', '3', '_', '1']
    if len(parts) == 5:
        net = parts[0].split('_')[0]
        if len(net) <= 3 and net.isalpha() and net.islower():
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
        incomplete_operators = []
        for _, _, operators, incomplete in settings.BOD_OPERATORS:
            if incomplete:
                incomplete_operators += operators.values()
            else:
                open_data_operators += operators.values()
        for _, _, _, operators in settings.PASSENGER_OPERATORS:
            open_data_operators += operators.values()
        for _, _, operators in settings.FIRST_OPERATORS:
            open_data_operators += operators.values()
        for _, _, _, operators in settings.STAGECOACH_OPERATORS:
            open_data_operators += operators.values()
        self.open_data_operators = set(open_data_operators)
        self.incomplete_operators = set(incomplete_operators)
        for archive_name in options['archives']:
            self.handle_archive(archive_name, options['files'])
        if self.undefined_holidays:
            print(self.undefined_holidays)

    def set_region(self, archive_name):
        archive_name = os.path.basename(archive_name)
        self.region_id, _ = os.path.splitext(archive_name)

        self.source, created = DataSource.objects.get_or_create(
            {
                'url': 'ftp://ftp.tnds.basemap.co.uk/' + archive_name
            },
            name=self.region_id
        )

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

    def mark_old_services_as_not_current(self):
        old_services = self.source.service_set.filter(current=True).exclude(id__in=self.service_ids)
        old_services.update(current=False)
        self.source.route_set.exclude(service__in=self.service_ids).delete()

    def handle_archive(self, archive_name, filenames):
        self.service_ids = set()

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
                            try:
                                self.handle_file(open_file, filename)
                            except (AttributeError, DataError) as error:
                                logger.error(error, exc_info=True)

        self.mark_old_services_as_not_current()

        self.source.save(update_fields=['datetime'])

        StopPoint.objects.filter(active=False, service__current=True).update(active=True)
        self.source.service_set.filter(current=False, geometry__isnull=False).update(geometry=None)

    def get_calendar(self, operating_profile, operating_period):
        calendar_dates = [
            CalendarDate(start_date=date_range.start, end_date=date_range.end, dates=date_range.dates(),
                         operation=False) for date_range in operating_profile.nonoperation_days
        ]
        calendar_dates += [
            CalendarDate(start_date=date_range.start, end_date=date_range.end, dates=date_range.dates(),
                         special=True, operation=True) for date_range in operating_profile.operation_days
        ]

        for holiday in operating_profile.operation_bank_holidays:
            if holiday in BANK_HOLIDAYS:
                if (holiday == 'AllBankHolidays' or holiday == 'HolidayMondays') and self.region_id == 'S':
                    continue
                date = BANK_HOLIDAYS[holiday]
                dates = DateRange(date, date, '[]')
                if operating_period.contains(date):
                    calendar_dates.append(
                        CalendarDate(start_date=date, end_date=date, dates=dates, special=True, operation=True)
                    )
            else:
                self.undefined_holidays.add(holiday)

        for holiday in operating_profile.nonoperation_bank_holidays:
            if holiday in BANK_HOLIDAYS:
                if (holiday == 'AllBankHolidays' or holiday == 'HolidayMondays') and self.region_id == 'S':
                    continue
                date = BANK_HOLIDAYS[holiday]
                dates = DateRange(date, date, '[]')
                if operating_period.contains(date):
                    calendar_dates.append(
                        CalendarDate(start_date=date, end_date=date, dates=dates, operation=False)
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

        # remove date ranges which end before they start?!
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

    def handle_journeys(self, route, stops, transxchange, txc_service, line_id):
        default_calendar = None

        stop_times = []

        trips = []
        notes_by_trip = []

        for journey in transxchange.journeys:
            if journey.service_ref != txc_service.service_code:
                continue
            if journey.line_ref != line_id:
                continue

            calendar = None
            if journey.operating_profile:
                calendar = self.get_calendar(journey.operating_profile, txc_service.operating_period)
            else:
                if not default_calendar:
                    default_calendar = self.get_calendar(txc_service.operating_profile, txc_service.operating_period)
                calendar = default_calendar

            if not calendar:
                continue

            trip = Trip(
                inbound=journey.journey_pattern.direction == 'inbound',
                calendar=calendar,
                route=route,
                journey_pattern=journey.journey_pattern.id,
            )

            for i, cell in enumerate(journey.get_times()):
                timing_status = cell.stopusage.timingstatus
                if timing_status is None or timing_status == 'otherPoint':
                    timing_status = 'OTH'
                elif timing_status == 'principleTimingPoint':
                    timing_status = 'PTP'
                stop_time = StopTime(
                    trip=trip,
                    arrival=cell.arrival_time,
                    departure=cell.departure_time,
                    sequence=i,
                    timing_status=timing_status,
                    activity=cell.stopusage.activity or ''
                )
                if i == 0:
                    trip.start = stop_time.arrival or stop_time.departure
                if cell.stopusage.stop.atco_code in stops:
                    stop_time.stop_id = cell.stopusage.stop.atco_code
                    trip.destination_id = stop_time.stop_id
                else:
                    stop_time.stop_code = cell.stopusage.stop.atco_code
                stop_times.append(stop_time)

            trip.end = stop_time.departure or stop_time.arrival
            trips.append(trip)

            notes = []
            for note in journey.notes:
                note_cache_key = f'{note}:{journey.notes[note]}'
                if note_cache_key in self.notes:
                    note = self.notes[note_cache_key]
                else:
                    note, _ = Note.objects.get_or_create(code=note or '', text=journey.notes[note])
                    self.notes[note_cache_key] = note
                notes.append(note)
            notes_by_trip.append(notes)

        Trip.objects.bulk_create(trips)

        for i, trip in enumerate(trips):
            if notes_by_trip[i]:
                trip.notes.set(notes_by_trip[i])

        for stop_time in stop_times:
            stop_time.trip = stop_time.trip  # set trip_id
        StopTime.objects.bulk_create(stop_times)

    def get_existing_service(self, line_name, operators):
        services = Service.objects.filter(operator__in=operators, line_name__iexact=line_name)
        services = services.select_related('source').defer('geometry')
        try:
            try:
                existing = services.get(current=True)
            except Service.DoesNotExist:
                existing = services.get()
        except (Service.DoesNotExist, Service.MultipleObjectsReturned):
            return
        if not existing:
            return

        if len(existing.source.name) <= 4:
            return existing

        if existing.service_code.startswith(f'{self.source.id}-'):
            return

        return existing

    def get_description(self, txc_service):
        description = txc_service.description
        if description and ('timetable' in description.lower() or 'Database Refresh' in description):
            description = None
        elif self.source.name.startswith('Arriva') or self.source.name.startswith('Stagecoach'):
            description = None
        if not description or self.source.name.startswith('Lynx'):
            origin = txc_service.origin
            destination = txc_service.destination
            if not (origin == 'Origin' and destination == 'Destination'):
                if origin.isupper() and destination.isupper():
                    origin = titlecase(origin)
                    destination = titlecase(destination)

                # for the outbound and inbound descriptions
                txc_service.description_parts = [origin, destination]

                if description and (description.startswith('via ') or description.startswith('then ')):
                    description = f'{origin} - {destination} {description}'
                else:
                    description = f'{origin} - {destination}'
                    vias = txc_service.vias
                    if vias:
                        if len(txc_service.vias) == 1 and (',' in vias[0] or ' and ' in vias[0] or '&' in vias[0]):
                            description = f"{description} via {', '.join(vias)}"
                        else:
                            description = [origin] + vias + [destination]
                            description = ' - '.join(description)
        if description and self.source.name == 'NE':
            description = sanitize_description(description)
        return description

    def is_tnds(self):
        return len(self.source.name) <= 4

    def handle_service(self, filename, parts, transxchange, txc_service, today, stops):
        if txc_service.operating_period.end and txc_service.operating_period.end < today:
            if not self.source.name.startswith('First'):
                return

        operators = self.get_operators(transxchange, txc_service)

        if self.is_tnds() and operators and all(operator.id in self.open_data_operators for operator in operators):
            return

        lines = get_lines(txc_service.element)

        linked_services = []

        description = self.get_description(txc_service)

        for line_id, line_name, line_brand in lines:
            existing = None

            if operators and description and line_name:
                if all(operator.parent == 'Go South Coast' for operator in operators):
                    existing = Service.objects.filter(operator__parent='Go South Coast')
                else:
                    existing = Service.objects.filter(operator__in=operators)
                existing = existing.filter(description=description, line_name=line_name)
                existing = existing.order_by('-current', 'service_code').first()

            if self.is_tnds():
                if operators and all(operator.id in self.incomplete_operators for operator in operators):
                    if Service.objects.filter(
                        operator__in=operators, line_name=line_name, current=True
                    ).exclude(source=self.source):
                        continue

                service_code = get_service_code(filename)
                if service_code is None:
                    service_code = txc_service.service_code

            else:
                operator_code = '-'.join(operator.id for operator in operators)
                if operator_code == 'TDTR' and 'Swindon-Rural' in filename:
                    operator_code = 'SBCR'

                if parts:
                    service_code = f'{self.source.id}-{parts}-{line_name}'
                    if not existing:
                        existing = Service.objects.filter(service_code=service_code, line_name=line_name).first()
                    if not existing:
                        existing = self.source.service_set.filter(
                            line_name=line_name, route__code__contains=f'/{parts}_'
                        ).order_by('-current', 'service_code').first()
                else:
                    service_code = f'{self.source.id}-{operator_code}-{txc_service.service_code}'
                    if len(lines) > 1:
                        service_code += '-' + line_name

                    if not existing and operator_code != 'SBCR':
                        existing = self.get_existing_service(line_name, operators)

            if not existing:
                existing = Service.objects.filter(service_code=service_code).first()
                if existing and existing.current and existing.line_name != line_name:
                    service_code = f'{service_code}-{line_name}'
                existing = None

            if existing:
                services = Service.objects.filter(id=existing.id)
            else:
                services = Service.objects.filter(service_code=service_code)

            defaults = {
                'line_name': line_name,
                'date': today,
                'current': True,
                'source': self.source,
                'show_timetable': True
            }
            if not existing:
                defaults['service_code'] = service_code

            if description:
                defaults['description'] = description

            if txc_service.mode:
                defaults['mode'] = txc_service.mode
            if line_brand:
                defaults['line_brand'] = line_brand
            if self.region_id:
                defaults['region_id'] = self.region_id

            line_strings = set()
            for pattern in txc_service.journey_patterns.values():
                line_string = line_string_from_journeypattern(pattern, stops)
                if line_string not in line_strings:
                    line_strings.add(line_string)
                multi_line_string = MultiLineString(*(ls for ls in line_strings if ls))

            defaults['geometry'] = multi_line_string

            if self.service_descriptions:  # NCSD
                defaults['outbound_description'], defaults['inbound_description'] = self.get_service_descriptions(
                    filename)
                defaults['description'] = defaults['outbound_description'] or defaults['inbound_description']

            try:
                service, service_created = services.update_or_create(defaults)
            except IntegrityError as e:
                print(e, service_code)
                continue

            if service_created:
                service.operator.set(operators)
            else:
                if service.slug == service_code.lower():
                    service.slug = ''
                    service.save(update_fields=['slug'])
                if service.id in self.service_ids or all(o.parent == 'Go South Coast' for o in operators):
                    service.operator.add(*operators)
                else:
                    service.operator.set(operators)
                if service.id not in self.service_ids:
                    service.route_set.all().delete()
                    # service.stops.clear()
            self.service_ids.add(service.id)
            linked_services.append(service.id)

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
                route_code += f'#{txc_service.service_code}'
            if len(lines) > 1:
                route_code += f'#{line_id}'

            route, route_created = Route.objects.update_or_create(route_defaults,
                                                                  source=self.source, code=route_code)
            if not route_created:
                route.trip_set.all().delete()

            self.handle_journeys(route, stops, transxchange, txc_service, line_id)

            service.stops.clear()
            outbound, inbound = get_stop_usages(Trip.objects.filter(route__service=service))
            stop_usages = [
                StopUsage(service=service, stop_id=stop_time.stop_id, timing_status=stop_time.timing_status,
                          direction='outbound', order=i)
                for i, stop_time in enumerate(outbound)
            ] + [
                StopUsage(service=service, stop_id=stop_time.stop_id, timing_status=stop_time.timing_status,
                          direction='inbound', order=i)
                for i, stop_time in enumerate(inbound)
            ]
            StopUsage.objects.bulk_create(stop_usages)

            changed_fields = []
            if outbound:
                outbound = Grouping(txc_service, outbound[0].stop, outbound[-1].stop)
                outbound_description = str(outbound)
                if outbound_description != service.outbound_description:
                    service.outbound_description = outbound_description
                    changed_fields.append('outbound_description')
            if inbound:
                inbound = Grouping(txc_service, inbound[0].stop, inbound[-1].stop)
                inbound_description = str(inbound)
                if inbound_description != service.inbound_description:
                    service.inbound_description = inbound_description
                    changed_fields.append('inbound_description')
            if changed_fields:
                service.save(update_fields=changed_fields)

            if service_code in self.corrections:
                corrections = {}
                for field in self.corrections[service_code]:
                    if field == 'operator':
                        service.operator.set(self.corrections[service_code][field])
                    else:
                        corrections[field] = self.corrections[service_code][field]
                Service.objects.filter(service_code=service_code).update(**corrections)

            if service_code == 'twm_5-501-A-y11':  # Lakeside Coaches
                Trip.objects.filter(route__service=service, start='15:05').delete()
                Trip.objects.filter(route__service=service, start='15:30').delete()

        if len(linked_services) > 1:
            for i, from_service in enumerate(linked_services):
                for i, to_service in enumerate(linked_services[i+1:]):
                    kwargs = {
                        'from_service_id': from_service,
                        'to_service_id': to_service,
                        'how': 'parallel'
                    }
                    if not ServiceLink.objects.filter(**kwargs).exists():
                        ServiceLink.objects.create(**kwargs)

    @staticmethod
    def do_stops(transxchange_stops):
        stops = StopPoint.objects.in_bulk(transxchange_stops.keys())
        stops_to_create = {atco_code: StopPoint(atco_code=atco_code, common_name=str(stop)[:48], active=True)
                           for atco_code, stop in transxchange_stops.items() if atco_code not in stops}
        if stops_to_create:
            StopPoint.objects.bulk_create(stops_to_create.values())
            stops = {**stops, **stops_to_create}

        return stops

    def get_filename_parts(self, filename):
        if self.source.name.startswith('Arriva') or self.source.name.startswith('Stagecoach'):
            parts = os.path.basename(filename)[:-4].split('_')
            if len(parts[-1]) < 3:
                parts = parts[:-1]
            assert len(parts[-1]) >= 8
            assert parts[-1].isdigit()
            return '_'.join(parts[:-1])

    def handle_file(self, open_file, filename):
        transxchange = TransXChange(open_file)

        today = self.source.datetime.date()

        stops = self.do_stops(transxchange.stops)

        parts = self.get_filename_parts(filename)

        for txc_service in transxchange.services.values():
            # if service.mode == 'underground':
            #     continue

            self.handle_service(filename, parts, transxchange, txc_service, today, stops)

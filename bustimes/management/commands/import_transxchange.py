"""
Usage:

    ./manage.py import_transxchange EA.zip [EM.zip etc]
"""

import logging
import os
import re
import csv
import yaml
import zipfile
import xml.etree.cElementTree as ET
import datetime
from psycopg2.extras import DateRange
from titlecase import titlecase
from django.conf import settings
from django.contrib.gis.geos import MultiLineString
from django.core.management.base import BaseCommand
from django.db import transaction, DataError, IntegrityError
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from busstops.models import Operator, Service, DataSource, StopPoint, StopUsage, ServiceCode, ServiceLink
from ...models import Route, Calendar, CalendarDate, Trip, StopTime, Note, Garage
from ...timetables import get_stop_usages
from transxchange.txc import TransXChange, sanitize_description_part, Grouping


logger = logging.getLogger(__name__)

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
    # 'ChristmasEve':     [datetime.date(2020, 12, 24)],
    # 'ChristmasDay':     [datetime.date(2020, 12, 25)],
    # 'BoxingDay':        [datetime.date(2020, 12, 26)],
    # 'BoxingDayHoliday': [datetime.date(2020, 12, 28)],
    # 'NewYearsEve':      [datetime.date(2020, 12, 31)],
    # 'NewYearsDay':      [datetime.date(2021, 1, 1)],
    # 'Jan2ndScotland':   [datetime.date(2021, 1, 2)],
    'GoodFriday':       [datetime.date(2021, 4, 2)],
    'EasterMonday':     [datetime.date(2021, 4, 5)],
    'MayDay':           [datetime.date(2021, 5, 3)],
    'SpringBank':       [datetime.date(2021, 5, 31)],
}

# BANK_HOLIDAYS['EarlyRunOffDays'] = BANK_HOLIDAYS['ChristmasEve'] + BANK_HOLIDAYS['NewYearsEve']
# BANK_HOLIDAYS['Christmas'] = BANK_HOLIDAYS['ChristmasDay'] + BANK_HOLIDAYS['BoxingDay']
# BANK_HOLIDAYS['AllHolidaysExceptChristmas'] = BANK_HOLIDAYS['NewYearsDay'] + BANK_HOLIDAYS[]
# BANK_HOLIDAYS['AllBankHolidays'] = BANK_HOLIDAYS['Christmas'] + BANK_HOLIDAYS['AllHolidaysExceptChristmas']
BANK_HOLIDAYS['EarlyRunOffDays'] = []
BANK_HOLIDAYS['Christmas'] = []
BANK_HOLIDAYS['AllHolidaysExceptChristmas'] = BANK_HOLIDAYS['GoodFriday'] + BANK_HOLIDAYS['EasterMonday'] + \
                                              BANK_HOLIDAYS['MayDay'] + BANK_HOLIDAYS['SpringBank']
BANK_HOLIDAYS['AllBankHolidays'] = BANK_HOLIDAYS['Christmas'] + BANK_HOLIDAYS['AllHolidaysExceptChristmas']


def initialisms(word, **kwargs):
    if word in ('YMCA', 'PH'):
        return word


def get_summary(summary):
    # London wtf
    if summary == 'not School vacation in free public holidays regulation holidays':
        return 'not school holidays'

    summary = summary.replace(' days days', ' days')
    summary = summary.replace('olidays holidays', 'olidays')
    summary = summary.replace('AnySchool', 'school')

    summary = re.sub(r'(?i)(school(day)?s)', 'school', summary)

    return summary


def sanitize_description(name):
    """
    Given an oddly formatted description from the North East,
    like 'Bus Station bay 5,Blyth - Grange Road turning circle,Widdrington Station',
    returns a shorter, more normal version like
    'Blyth - Widdrington Station'
    """

    parts = [sanitize_description_part(part) for part in name.split(' - ')]
    return ' - '.join(parts)


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


def get_operator_name(operator_element):
    "Given an Operator element, returns the operator name or None"

    for element_name in ('TradingName', 'OperatorNameOnLicence', 'OperatorShortName'):
        name = operator_element.findtext(element_name)
        if name:
            return name.replace('&amp;', '&')


def get_operator_by(scheme, code):
    if code:
        try:
            return Operator.objects.filter(operatorcode__code=code, operatorcode__source__name=scheme).distinct().get()
        except (Operator.DoesNotExist, Operator.MultipleObjectsReturned):
            pass


class Command(BaseCommand):
    @staticmethod
    def add_arguments(parser):
        parser.add_argument('archives', nargs=1, type=str)
        parser.add_argument('files', nargs='*', type=str)

    def set_up(self):
        self.calendar_cache = {}
        self.undefined_holidays = set()
        self.missing_operators = []
        self.notes = {}
        self.corrections = {}
        self.garages = {}

    def handle(self, *args, **options):
        self.set_up()

        open_data_operators = []
        incomplete_operators = []
        for operator_code, _, operators, incomplete in settings.BOD_OPERATORS:
            if operators:
                operators = operators.values()
            else:
                operators = [operator_code]
            if incomplete:
                incomplete_operators += operators
            else:
                open_data_operators += operators
        for _, _, _, operators in settings.PASSENGER_OPERATORS:
            open_data_operators += operators.values()
        for _, _, operators in settings.FIRST_OPERATORS:
            open_data_operators += operators.values()
        for _, _, _, operators in settings.STAGECOACH_OPERATORS:
            open_data_operators += operators.values()
        for _, operators, _ in settings.TICKETER_OPERATORS:
            open_data_operators += operators

        if 'SCLI' in open_data_operators:  # stagecoach lincs – cos a bloke complained about missing school services
            open_data_operators.remove('SCLI')
            incomplete_operators.append('SCLI')
        incomplete_operators.append('SEMM')  # h semmence & co

        self.open_data_operators = set(open_data_operators)
        self.incomplete_operators = set(incomplete_operators)
        for archive_name in options['archives']:
            self.handle_archive(archive_name, options['files'])

        self.debrief()

    def debrief(self):
        if self.undefined_holidays:
            print(self.undefined_holidays)
        for operator in self.missing_operators:
            print(operator)

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

        operator_code = operator_element.findtext('NationalOperatorCode')
        operator = get_operator_by('National Operator Codes', operator_code)
        if operator:
            return operator

        licence_number = operator_element.findtext('LicenceNumber')
        if licence_number:
            if licence_number.startswith('YW'):
                licence_number = licence_number.replace('YW', 'PB')
            try:
                return Operator.objects.get(licences__licence_number=licence_number)
            except (Operator.DoesNotExist, Operator.MultipleObjectsReturned):
                pass

        name = get_operator_name(operator_element)

        try:
            return Operator.objects.get(name=name)
        except (Operator.DoesNotExist, Operator.MultipleObjectsReturned):
            pass

        # Get by regional operator code
        operator_code = operator_element.findtext('OperatorCode')
        if operator_code:
            if not self.is_tnds():
                operator_code = self.operators.get(operator_code, operator_code)
            operator = get_operator_by(self.region_id, operator_code)
            if not operator:
                operator = get_operator_by('National Operator Codes', operator_code)
            if operator:
                return operator

        self.missing_operators.append(ET.tostring(operator_element, encoding="unicode"))

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
        self.source.route_set.exclude(id__in=self.route_ids).delete()

    def handle_archive(self, archive_name, filenames):
        self.service_ids = set()
        self.route_ids = set()

        self.set_region(archive_name)

        self.source.datetime = datetime.datetime.fromtimestamp(os.path.getmtime(archive_name), timezone.utc)

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

        self.update_geometries()

        self.source.save(update_fields=['datetime'])

        if not filenames:
            self.mark_old_services_as_not_current()
            self.source.service_set.filter(current=False, geometry__isnull=False).update(geometry=None)

        StopPoint.objects.filter(active=False, service__current=True).update(active=True)

    def update_geometries(self):
        for service in Service.objects.filter(id__in=self.service_ids):
            service.update_geometry()

    def get_calendar(self, operating_profile, operating_period):
        calendar_dates = [
            CalendarDate(start_date=date_range.start, end_date=date_range.end, dates=date_range.dates(),
                         operation=False) for date_range in operating_profile.nonoperation_days
        ]
        calendar_dates += [
            CalendarDate(start_date=date_range.start, end_date=date_range.end, dates=date_range.dates(),
                         special=True, operation=True) for date_range in operating_profile.operation_days
        ]

        dates = []
        for holiday in operating_profile.operation_bank_holidays:
            if holiday in BANK_HOLIDAYS:
                for date in BANK_HOLIDAYS[holiday]:
                    if operating_period.contains(date):
                        if date not in dates:
                            dates.append(date)
                            calendar_dates.append(
                                CalendarDate(
                                    start_date=date, end_date=date,
                                    dates=DateRange(date, date, '[]'),
                                    special=True, operation=True,
                                    summary=holiday
                                )
                            )
            else:
                self.undefined_holidays.add(holiday)

        dates = []
        for holiday in operating_profile.nonoperation_bank_holidays:
            if holiday in BANK_HOLIDAYS:
                for date in BANK_HOLIDAYS[holiday]:
                    if operating_period.contains(date):
                        if date not in dates:
                            dates.append(date)
                            calendar_dates.append(
                                CalendarDate(
                                    start_date=date, end_date=date,
                                    dates=DateRange(date, date, '[]'),
                                    operation=False,
                                    summary=holiday
                                )
                            )
            else:
                self.undefined_holidays.add(holiday)

        sodt = operating_profile.serviced_organisation_day_type
        summary = ''
        if sodt:
            if sodt.nonoperation_workingdays:
                if sodt.nonoperation_workingdays.name:
                    summary = f'not {sodt.nonoperation_workingdays.name} days'
                nonoperation_days = sodt.nonoperation_workingdays.working_days
            elif sodt.nonoperation_holidays:
                if sodt.nonoperation_holidays.name:
                    summary = f'not {sodt.nonoperation_holidays.name} holidays'
                nonoperation_days = sodt.nonoperation_holidays.holidays
            else:
                nonoperation_days = None

            if nonoperation_days:
                calendar_dates += [
                    CalendarDate(start_date=date_range.start, end_date=date_range.end, dates=date_range.dates(),
                                 operation=False)
                    for date_range in nonoperation_days
                ]

            if sodt.operation_workingdays:
                if sodt.operation_workingdays.name:
                    summary = f'{sodt.operation_workingdays.name} days only'
                operation_days = sodt.operation_workingdays.working_days
            elif sodt.operation_holidays:
                if sodt.operation_holidays.name:
                    summary = f'{sodt.operation_holidays.name} holidays only'
                operation_days = sodt.operation_holidays.holidays
            else:
                operation_days = None

            if operation_days:
                calendar_dates += [
                    CalendarDate(start_date=date_range.start, end_date=date_range.end, dates=date_range.dates(),
                                 operation=True)
                    for date_range in operation_days
                ]

        # remove date ranges which end before they start?! etc
        calendar_dates = [dates for dates in calendar_dates if dates.relevant(operating_period)]

        if operating_period.start == operating_period.end:
            if summary:
                summary = f"{summary}, "
            summary = f"{summary}{operating_period.start.strftime('%A %-d %B %Y')} only"

        if not calendar_dates and not operating_profile.regular_days and not summary:
            return

        calendar_hash = f'{operating_profile.regular_days}{operating_period.dates()}{summary}'
        calendar_hash += ''.join(f'{date.dates}{date.operation}{date.special}' for date in calendar_dates)

        if calendar_hash in self.calendar_cache:
            return self.calendar_cache[calendar_hash]

        if summary:
            summary = get_summary(summary)

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
            dates=operating_period.dates(),
            summary=summary
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

    def handle_journeys(self, route, stops, journeys, txc_service, line_id):
        default_calendar = None

        stop_times = []

        trips = []
        notes_by_trip = []

        for journey in journeys:
            calendar = None
            if journey.operating_profile:
                calendar = self.get_calendar(journey.operating_profile, txc_service.operating_period)
            elif journey.journey_pattern.operating_profile:
                calendar = self.get_calendar(journey.journey_pattern.operating_profile, txc_service.operating_period)
            else:
                if not default_calendar:
                    default_calendar = self.get_calendar(txc_service.operating_profile, txc_service.operating_period)
                calendar = default_calendar

            if calendar is None:
                continue

            trip = Trip(
                inbound=journey.journey_pattern.direction == 'inbound',
                calendar=calendar,
                route=route,
                journey_pattern=journey.journey_pattern.id,
                ticket_machine_code=journey.ticket_machine_journey_code or '',
                block=journey.block or ''
            )

            if journey.garage_ref:
                trip.garage = self.garages[journey.garage_ref]

            blank = False
            for i, cell in enumerate(journey.get_times()):
                timing_status = cell.stopusage.timingstatus
                if timing_status is None:
                    timing_status = ''
                    blank = True
                elif len(timing_status) > 3:
                    if timing_status == 'otherPoint':
                        timing_status = 'OTH'
                    elif timing_status == 'principleTimingPoint' or timing_status == 'principalTimingPoint':
                        timing_status = 'PTP'
                    else:
                        print(timing_status)

                stop_time = StopTime(
                    trip=trip,
                    sequence=i,
                    timing_status=timing_status,
                    activity=cell.stopusage.activity or ''
                )
                if stop_time.activity == 'pickUp' or stop_time.activity == 'pass':
                    stop_time.set_down = False
                if stop_time.activity == 'setDown' or stop_time.activity == 'pass':
                    stop_time.pick_up = False

                stop_time.departure = cell.departure_time
                if cell.arrival_time != cell.departure_time:
                    stop_time.arrival = cell.arrival_time
                if i == 0:
                    trip.start = stop_time.arrival_or_departure()
                atco_code = cell.stopusage.stop.atco_code
                if atco_code in stops:
                    if type(stops[atco_code]) is str:
                        stop_time.stop_code = stops[atco_code]
                    else:
                        stop_time.stop_id = cell.stopusage.stop.atco_code
                        trip.destination_id = stop_time.stop_id
                else:
                    stop_time.stop_code = atco_code
                stop_times.append(stop_time)

            # last stop
            if not stop_time.arrival:
                stop_time.arrival = stop_time.departure
                stop_time.departure = None
            trip.end = stop_time.departure_or_arrival()
            trips.append(trip)

            if blank and any(stop_time.timing_status for stop_time in stop_times):
                # not all timing statuses are blank - mark any blank ones as minor
                for stop_time in stop_times:
                    if not stop_time.timing_status:
                        stop_time.timing_status = 'OTH'

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

    def get_description(self, txc_service):
        description = txc_service.description
        if description and ('timetable' in description.lower() or 'Database Refresh' in description):
            description = None
        elif (
            self.source.name.startswith('Stagecoach')
            or self.source.name.startswith('Coach Services')
            or self.source.name.startswith('Sanders')
        ):
            description = None
        if not description:
            origin = txc_service.origin
            destination = txc_service.destination
            if origin and destination and (origin != 'Origin' and destination != 'Destination' or txc_service.vias):
                if origin.isupper() and destination.isupper():
                    origin = titlecase(origin, callback=initialisms)
                    destination = titlecase(destination, callback=initialisms)

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
        return self.source.url.startswith('ftp://ftp.tnds.basemap.co.uk/')

    def should_defer_to_other_source(self, operators, line_name):
        if self.source.name == 'L':
            return False
        if operators and all(operator.id in self.incomplete_operators for operator in operators):
            services = Service.objects.filter(line_name__iexact=line_name, current=True).exclude(source=self.source)
            if services.filter(operator__in=operators).exists():
                return True
            if any(operator.id == 'SCLI' for operator in operators):
                return services.filter(operator__parent='Stagecoach').exists()

    def handle_service(self, filename, transxchange, txc_service, today, stops):
        if txc_service.operating_period.end:
            if txc_service.operating_period.end < today:
                print(filename, txc_service.operating_period.end)
                return
            elif txc_service.operating_period.end < txc_service.operating_period.start:
                return

        operators = self.get_operators(transxchange, txc_service)

        if not operators:
            basename = os.path.basename(filename)  # e.g. 'KCTB_'
            if basename[4] == '_':
                maybe_operator_code = basename[:4]
                if maybe_operator_code.isupper() and maybe_operator_code.isalpha():
                    try:
                        operators = [Operator.objects.get(id=maybe_operator_code)]
                    except Operator.DoesNotExist:
                        pass

        if self.is_tnds() and self.source.name != 'L':
            if operators and all(operator.id in self.open_data_operators for operator in operators):
                return

        linked_services = []

        description = self.get_description(txc_service)

        if description == 'Origin - Destination':
            description = ''

        for line in txc_service.lines:
            existing = None
            service_code = None

            if operators and line.line_name:
                if self.source.name in {'Go South West', 'Oxford Bus Company'}:
                    assert operators[0].parent
                    existing = Service.objects.filter(operator__parent=operators[0].parent)

                    if self.source.name == 'Oxford Bus Company':
                        if txc_service.service_code.startswith('T'):
                            operators = Operator.objects.filter(id='THTR')
                        elif txc_service.service_code.startswith('C'):
                            operators = Operator.objects.filter(id='CSLB')
                    elif self.source.name == 'Go South West':
                        if txc_service.service_code.startswith('GC'):
                            operators = Operator.objects.filter(id='TFCN')

                elif all(operator.parent == 'Go South Coast' for operator in operators):
                    existing = Service.objects.filter(operator__parent='Go South Coast')
                elif self.source.name.startswith('Stagecoach'):
                    existing = Service.objects.filter(Q(source=self.source) | Q(operator__in=operators))
                    if description:
                        existing = existing.filter(description=description)
                else:
                    existing = Service.objects.filter(operator__in=operators)

                if len(transxchange.services) == 1:
                    has_stop_time = Exists(StopTime.objects.filter(stop__in=stops, trip__route__service=OuterRef('id')))
                    has_stop_usage = Exists(StopUsage.objects.filter(stop__in=stops, service=OuterRef('id')))
                    has_no_route = ~Exists(Route.objects.filter(service=OuterRef('id')))
                    existing = existing.filter(has_stop_time | (has_stop_usage & has_no_route))
                elif len(txc_service.lines) == 1:
                    existing = existing.filter(
                        Exists(
                            Route.objects.filter(service_code=txc_service.service_code, service=OuterRef('id'))
                        )
                    )
                elif description:
                    existing = existing.filter(description=description)

                existing = existing.filter(line_name__iexact=line.line_name).order_by('-current', 'id').first()

            if self.is_tnds():
                if self.should_defer_to_other_source(operators, line.line_name):
                    continue

                service_code = get_service_code(filename)
                if service_code is None:
                    service_code = txc_service.service_code

                if not existing:
                    # assume service code is at least unique within a TNDS region
                    existing = self.source.service_set.filter(service_code=service_code).first()
            elif re.match(r'^P[BCDFGHKM]\d+:\d+.*.$', txc_service.service_code):
                service_code = txc_service.service_code

            if existing:
                service = existing
            else:
                service = Service()

            service.line_name = line.line_name
            service.date = today
            service.current = True
            service.source = self.source
            service.show_timetable = True

            if service_code:
                service.service_code = service_code

            if description:
                service.description = description

            line_brand = line.line_brand
            if txc_service.marketing_name and txc_service.marketing_name != 'CornwallbyKernow':
                line_brand = txc_service.marketing_name
                if line.line_name in line_brand:
                    line_brand_parts = line_brand.split()
                    if line.line_name in line_brand_parts:
                        line_brand_parts.remove(line.line_name)
                        line_brand = ' '.join(line_brand_parts)
                print(line_brand)
            if line_brand:
                service.line_brand = line_brand

            if txc_service.mode:
                service.mode = txc_service.mode

            if self.region_id:
                service.region_id = self.region_id

            if self.service_descriptions:  # NCSD
                service.outbound_description, service.inbound_description = self.get_service_descriptions(filename)
                service.description = service.outbound_description or service.inbound_description

            if service.id:
                service_created = False
            else:
                service_created = True
            service.save()

            if not service_created:
                if '_' in service.slug or '-' not in service.slug or existing and not existing.current:
                    service.slug = ''
                    service.save(update_fields=['slug'])

            if operators:
                if service_created:
                    service.operator.set(operators)
                else:
                    if self.source.name in {'Oxford Bus Company', 'Go South West'}:
                        pass
                    elif service.id in self.service_ids or all(o.parent == 'Go South Coast' for o in operators):
                        service.operator.add(*operators)
                    else:
                        service.operator.set(operators)
            self.service_ids.add(service.id)
            linked_services.append(service.id)

            journeys = transxchange.get_journeys(txc_service.service_code, line.id)

            if journeys:
                journey = journeys[0]

                ticket_machine_service_code = journey.ticket_machine_service_code
                if ticket_machine_service_code and ticket_machine_service_code != line.line_name:
                    try:
                        ServiceCode.objects.create(scheme='SIRI', code=ticket_machine_service_code, service=service)
                    except IntegrityError:
                        pass

                # a code used in Traveline Cymru URLs:
                if self.source.name == 'W':
                    private_code = journey.private_code
                    if private_code and ':' in private_code:
                        ServiceCode.objects.update_or_create({
                            'code': private_code.split(':', 1)[0]
                        }, service=service, scheme='Traveline Cymru')

            # timetable data:

            route_defaults = {
                'line_name': line.line_name,
                'line_brand': line_brand,
                'start_date': txc_service.operating_period.start,
                'end_date': txc_service.operating_period.end,
                'dates': txc_service.operating_period.dates(),
                'service': service,
                'revision_number': transxchange.attributes['RevisionNumber'],
                'service_code': txc_service.service_code
            }
            if description:
                route_defaults['description'] = description

            geometry = []
            if transxchange.route_sections:
                patterns = {
                    journey.journey_pattern.id: journey.journey_pattern for journey in journeys
                }
                routes = [pattern.route_ref for pattern in patterns.values() if pattern.route_ref]
                if routes:
                    routes = [transxchange.routes[route_id] for route_id in transxchange.routes if route_id in routes]
                    for route in routes:
                        for section_ref in route.route_section_refs:
                            section = transxchange.route_sections[section_ref]
                            for link in section.links:
                                if link.track:
                                    geometry.append(link.track)
                else:
                    route_links = {}
                    for section in transxchange.route_sections.values():
                        for link in section.links:
                            route_links[link.id] = link
                    for journey in journeys:
                        if journey.journey_pattern:
                            for section in journey.journey_pattern.sections:
                                for link in section.timinglinks:
                                    link = route_links[link.route_link_ref]
                                    if link.track:
                                        geometry.append(link.track)
                if geometry:
                    geometry = MultiLineString(geometry).simplify()
                    if not isinstance(geometry, MultiLineString):
                        geometry = MultiLineString(geometry)
                    route_defaults['geometry'] = geometry

            route_code = filename
            if len(transxchange.services) > 1:
                route_code += f'#{txc_service.service_code}'
            if len(txc_service.lines) > 1:
                route_code += f'#{line.id}'

            route, route_created = Route.objects.update_or_create(route_defaults,
                                                                  source=self.source, code=route_code)
            self.route_ids.add(route.id)
            if not route_created:
                # if 'opendata.ticketer' in self.source.url and route.service_id == service_id:
                #     continue
                route.trip_set.all().delete()

            self.handle_journeys(route, stops, journeys, txc_service, line.id)

            service.stops.clear()
            outbound, inbound = get_stop_usages(Trip.objects.filter(route__service=service))

            changed_fields = []

            if self.source.name.startswith('Arriva ') or self.source.name == 'Yorkshire Tiger':
                if outbound:
                    changed = 0
                    origin_stop = outbound[0].stop
                    destination_stop = outbound[-1].stop
                    if txc_service.origin in origin_stop.common_name:
                        if origin_stop.locality.name not in txc_service.origin:
                            txc_service.origin = f'{origin_stop.locality.name} {txc_service.origin}'
                        changed += 1
                    if txc_service.destination in destination_stop.common_name:
                        if destination_stop.locality.name not in txc_service.destination:
                            txc_service.destination = f'{destination_stop.locality.name} {txc_service.destination}'
                        changed += 1
                    if changed == 2:
                        service.description = f'{txc_service.origin} - {txc_service.destination}'
                        changed_fields.append('description')

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

            service_code = service.service_code
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

            elif service_code == 'bed_44-34-_-y08':  # Sanders 34 Happisburgh - Stalham
                StopTime.objects.filter(
                    trip__route__service=service,
                    trip__start='16:15',
                    arrival__gte='16:50'
                ).update(activity='setDown')

            service.update_search_vector()

        if len(linked_services) > 1:
            for i, from_service in enumerate(linked_services):
                for i, to_service in enumerate(linked_services[i+1:]):
                    kwargs = {
                        'from_service_id': from_service,
                        'to_service_id': to_service,
                    }
                    if not ServiceLink.objects.filter(**kwargs).exists():
                        ServiceLink.objects.create(**kwargs, how='also')

    @staticmethod
    def do_stops(transxchange_stops):
        stops = StopPoint.objects.in_bulk(transxchange_stops.keys())
        stops_to_create = {}
        for atco_code, stop in transxchange_stops.items():
            if atco_code not in stops:
                if atco_code.startswith('000'):
                    stops[atco_code] = str(stop)[:255]
                else:
                    stops_to_create[atco_code] = StopPoint(atco_code=atco_code, common_name=str(stop)[:48], active=True)

        if stops_to_create:
            StopPoint.objects.bulk_create(stops_to_create.values())
            stops = {**stops, **stops_to_create}

        return stops

    def handle_file(self, open_file, filename):
        transxchange = TransXChange(open_file)

        today = self.source.datetime.date()

        stops = self.do_stops(transxchange.stops)

        for garage_code in transxchange.garages:
            if garage_code not in self.garages:
                garage = transxchange.garages[garage_code]
                name = garage.findtext('GarageName', '')
                try:
                    garage = Garage.objects.get(code=garage_code, name=name)
                except Garage.DoesNotExist:
                    garage = Garage.objects.create(code=garage_code, name=name)
                self.garages[garage_code] = garage

        for txc_service in transxchange.services.values():
            if txc_service.mode == 'underground':
                continue

            self.handle_service(filename, transxchange, txc_service, today, stops)

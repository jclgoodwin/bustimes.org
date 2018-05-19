"""Represent TransXChange concepts, and generate a matrix timetable from
TransXChange documents
"""
import os
import re
import xml.etree.cElementTree as ET
import calendar
import datetime
import ciso8601
import difflib
from functools import cmp_to_key
from django.utils.text import slugify
from titlecase import titlecase

NS = {
    'txc': 'http://www.transxchange.org.uk/'
}
# A safe date, far from any daylight savings changes or leap seconds
DUMMY_DATE = datetime.date(2016, 4, 5)
DESCRIPTION_REGEX = re.compile(r'.+,([^ ].+)$')
DURATION_REGEX = re.compile(
    r'P((?P<days>-?\d+?)D)?T((?P<hours>-?\d+?)H)?((?P<minutes>-?\d+?)M)?((?P<seconds>-?\d+?)S)?'
)
WEEKDAYS = {day: i for i, day in enumerate(calendar.day_name)}
BANK_HOLIDAYS = {
    datetime.date(2016, 12, 26): ('BoxingDay',),
    datetime.date(2017, 4, 14): ('GoodFriday',),
    datetime.date(2017, 4, 17): ('EasterMonday', 'HolidayMondays'),
    datetime.date(2017, 5, 1): ('MayDay', 'HolidayMondays'),
    datetime.date(2017, 5, 29): ('SpringBank', 'HolidayMondays'),
    datetime.date(2017, 8, 7): ('AugustBankHolidayScotland',),
    datetime.date(2017, 8, 28): ('LateSummerBankHolidayNotScotland', 'HolidayMondays'),
    datetime.date(2017, 12, 24): ('ChristmasEve',),
    datetime.date(2017, 12, 25): ('ChristmasDay', 'ChristmasDayHoliday'),
    datetime.date(2017, 12, 26): ('BoxingDay', 'BoxingDayHoliday'),
    datetime.date(2017, 12, 31): ('NewYearsEve',),
    datetime.date(2018, 1, 1): ('NewYearsDay', 'NewYearsDayHoliday', 'HolidayMondays'),
    datetime.date(2018, 3, 30): ('GoodFriday',),
    datetime.date(2018, 4, 2): ('EasterMonday', 'HolidayMondays'),
    datetime.date(2018, 5, 7): ('MayDay', 'HolidayMondays'),
    datetime.date(2018, 5, 28): ('SpringBank', 'HolidayMondays'),
    datetime.date(2018, 8, 6): ('AugustBankHolidayScotland',),
    datetime.date(2017, 8, 27): ('LateSummerBankHolidayNotScotland',),
}


def parse_duration(string):
    """Given an ISO 8601 formatted duration string like "PT2M", return a timedelta.

    Unlike django.utils.dateparse parse_duration, may return a negative timedelta
    """
    matches = iter(DURATION_REGEX.match(string).groupdict().items())
    params = {
        key: int(value) for key, value in matches if value is not None
    }
    return datetime.timedelta(**params)


def time_between(end, start):
    """Return the timedelta between two times (by converting them to datetimes)."""
    return datetime.datetime.combine(DUMMY_DATE, end) - datetime.datetime.combine(DUMMY_DATE, start)


def add_time(time, delta):
    """Add a timededelta the delta between two times (by naively converting them to datetimes)."""
    return (datetime.datetime.combine(DUMMY_DATE, time) + delta).time()


def sanitize_description_part(part):
    """Given an oddly formatted part like 'Bus Station bay 5,Blyth',
    return a shorter, more normal version like 'Blyth'.
    """
    sanitized_part = DESCRIPTION_REGEX.match(part.strip())
    return sanitized_part.group(1) if sanitized_part is not None else part


def correct_description(description):
    """Given an description, return a version with any typos pedantically corrected."""
    for old, new in (
            ('Stitians', 'Stithians'),
            ('Kings Lynn', "King's Lynn"),
            ('Wells - Next - The - Sea', 'Wells-next-the-Sea'),
            ('Wells next the Sea', 'Wells-next-the-Sea'),
            ('Baasingstoke', 'Basingstoke'),
            ('Liskerard', 'Liskeard'),
            ('Tauton', 'Taunton'),
            ('City Centre,st Stephens Street', 'Norwich'),
            ('Charlton Horethore', 'Charlton Horethorne'),
            ('Camleford', 'Camelford'),
            ('Tinagel', 'Tintagel'),
            ('- ', ' - '),
            (' -', ' - '),
            ('  -', ' -'),
            ('-  ', '- '),
    ):
        description = description.replace(old, new)
    return description


class Stop(object):
    """A TransXChange StopPoint."""
    stop = None
    locality = None

    def __init__(self, element):
        self.atco_code = element.find('txc:StopPointRef', NS).text or ''
        self.common_name = element.find('txc:CommonName', NS)
        self.locality = element.find('txc:LocalityName', NS)
        if self.common_name is not None:
            self.common_name = self.common_name.text
        if self.locality is not None:
            self.locality = self.locality.text

    def __str__(self):
        if not self.locality or self.locality in self.common_name:
            return self.common_name or self.atco_code
        return '%s %s' % (self.locality, self.common_name)

    def is_at(self, text):
        """Whether a given slugified string, roughly matches either
        this stop's locality's name, or this stop's name
        (e.g. 'kings-lynn' matches 'kings-lynn-bus-station' and vice versa).
        """
        name = slugify(self.stop.locality if self.stop else self.locality)
        if name != 'none' and name in text or text in name:
            if name == text:
                return 2
            return 1
        name = slugify(self.common_name)
        if text in name or name in text:
            if name == text:
                return 2
            return 1
        return False


class Row(object):
    """A row in a grouping in a timetable.
    Each row is associated with a Stop, and a list of times.
    """
    def __init__(self, part):
        self.part = part
        part.row = self
        self.times = []
        self.sequencenumbers = set()

    def is_minor(self):
        return self.part.timingstatus == 'OTH' or self.part.timingstatus == 'TIP'

    def __repr__(self):
        return str(self.part.stop)

    def get_order(self):
        for number in self.sequencenumbers:
            return number


class Cell(object):
    """Represents a special cell in a timetable, spanning multiple rows and columns,
    with some text like 'then every 5 minutes until'.
    """
    def __init__(self, colspan, rowspan, duration):
        self.colspan = colspan
        self.rowspan = self.min_height = rowspan
        self.duration = duration

    def __str__(self):
        if self.duration.seconds == 3600:
            if self.min_height < 3:
                return 'then\u00A0hourly until'
            return 'then hourly until'
        if self.duration.seconds % 3600 == 0:
            duration = '{} hours'.format(int(self.duration.seconds / 3600))
        else:
            duration = '{} minutes'.format(int(self.duration.seconds / 60))
        if self.min_height < 3:
            return 'then\u00A0every {}\u00A0until'.format(duration.replace(' ', '\u00A0'))
        if self.min_height < 4:
            return 'then every\u00A0{} until'.format(duration.replace(' ', '\u00A0'))
        return 'then every {} until'.format(duration)


class Grouping(object):
    """Probably either 'outbound' or 'inbound'.
    (Could perhaps be extended to group by weekends, bank holidays in the future).
    """
    def __init__(self, direction, parent):
        self.direction = direction
        self.parent = parent
        self.description_parts = None
        self.column_feet = {}
        self.journeypatterns = []
        self.journeys = []
        self.rows = []

    def get_order(self):
        if len(self.journeys):
            return self.journeys[0].departure_time
        return datetime.time()

    def has_minor_stops(self):
        for row in self.rows:
            if row.is_minor():
                return True
        return False

    def is_wide(self):
        return len(self.rows[0].times) > 3

    def starts_at(self, locality_name):
        return self.rows and self.rows[0].part.stop.is_at(locality_name)

    def ends_at(self, locality_name):
        return self.rows and self.rows[-1].part.stop.is_at(locality_name)

    def do_heads_and_feet(self):
        if all(len(row.sequencenumbers) == 1 for row in self.rows):
            self.rows.sort(key=Row.get_order)

        journeys = [vj for vj in self.journeys if vj.should_show(self.parent.date, self.parent)]
        if not journeys:
            return

        prev_journey = None
        in_a_row = 0
        prev_difference = None
        difference = None

        for i, journey in enumerate(journeys):
            for key in journey.notes:
                if key in self.column_feet:
                    if key in prev_journey.notes and prev_journey.notes[key] == journey.notes[key]:
                        self.column_feet[key][-1].span += 1
                    else:
                        self.column_feet[key].append(ColumnFoot(journey.notes[key], 1))
                else:
                    if i:
                        self.column_feet[key] = [ColumnFoot(None, i), ColumnFoot(journey.notes[key], 1)]
                    else:
                        self.column_feet[key] = [ColumnFoot(journey.notes[key], 1)]
            for key in self.column_feet:
                if key not in journey.notes:
                    if not self.column_feet[key][-1].notes:
                        self.column_feet[key][-1].span += 1
                    else:
                        self.column_feet[key].append(ColumnFoot(None, 1))

            if prev_journey:
                if prev_journey.notes != journey.notes:
                    if in_a_row > 1:
                        abbreviate(self, i, in_a_row - 1, prev_difference)
                    in_a_row = 0
                elif prev_journey.journeypattern.id == journey.journeypattern.id:
                    difference = time_between(journey.departure_time, prev_journey.departure_time)
                    if difference == prev_difference:
                        in_a_row += 1
                    else:
                        if in_a_row > 1:
                            abbreviate(self, i, in_a_row - 1, prev_difference)
                        in_a_row = 0
                else:
                    if in_a_row > 1:
                        abbreviate(self, i, in_a_row - 1, prev_difference)
                    in_a_row = 0

            prev_difference = difference
            difference = None
            prev_journey = journey

        if in_a_row > 1:
            abbreviate(self, len(journeys), in_a_row - 1, prev_difference)
        for row in self.rows:
            row.times = [time for time in row.times if time is not None]

    def __str__(self):
        parts = self.description_parts or self.parent.description_parts

        if parts:
            start = slugify(parts[0])
            end = slugify(parts[-1])

            same_score = self.starts_at(start) + self.ends_at(end)
            reverse_score = self.starts_at(end) + self.ends_at(start)

            if same_score > reverse_score or (reverse_score == 4 and same_score == 4):
                description = ' - '.join(parts)
            elif same_score < reverse_score:
                description = ' - '.join(reversed(parts))
            else:
                description = None

            if description:
                if self.parent.via:
                    description += ' via ' + self.parent.via
                return description

        return self.direction.capitalize()


class JourneyPattern(object):
    """A collection of JourneyPatternSections, in order."""
    def __init__(self, element, sections, groupings, routes):
        self.id = element.attrib.get('id')
        # self.journeys = []
        self.sections = [
            sections[section_element.text]
            for section_element in element.findall('txc:JourneyPatternSectionRefs', NS)
            if section_element.text in sections
        ]

        # the rows traversed by this journey pattern
        rows = []
        for section in self.sections:
            for timinglink in section.timinglinks:
                if not rows:
                    rows.append(Row(timinglink.origin))
                rows.append(Row(timinglink.destination))

        self.grouping = self.get_grouping(element, groupings, routes)
        self.grouping.journeypatterns.append(self)

        if not rows:
            return

        # this grouping's current rows (an amalgamation from any previously handled journey patterns)
        previous_list = [row.part.stop.atco_code for row in self.grouping.rows]

        # this journey pattern again
        current_list = [row.part.stop.atco_code for row in rows]
        diff = difflib.ndiff(previous_list, current_list)

        i = 0
        first = True
        for row in rows:
            if i < len(self.grouping.rows):
                existing_row = self.grouping.rows[i]
            else:
                existing_row = None
            instruction = next(diff)
            while instruction[0] in '-?':
                if instruction[0] == '-':
                    i += 1
                    if i < len(self.grouping.rows):
                        existing_row = self.grouping.rows[i]
                    else:
                        existing_row = None
                instruction = next(diff)

            assert instruction[2:] == row.part.stop.atco_code

            if instruction[0] == '+':
                if not existing_row:
                    self.grouping.rows.append(row)
                else:
                    self.grouping.rows = self.grouping.rows[:i] + [row] + self.grouping.rows[i:]
                existing_row = row
            else:
                assert instruction[2:] == existing_row.part.stop.atco_code
                row.part.row = existing_row

            if first:
                existing_row.first = True  # row is the first row of this pattern
                first = False
            if row.part.sequencenumber:
                existing_row.sequencenumbers.add(row.part.sequencenumber)
            i += 1

        existing_row.last = True  # row is the last row of this pattern

    def get_grouping(self, element, groupings, routes):
        route = element.find('txc:RouteRef', NS)
        if route is not None:
            route_id = route.text
            route = routes.get(route_id)

        direction_element = element.find('txc:Direction', NS)

        if direction_element is None or direction_element.text == 'outbound':
            return groupings['outbound']
        else:
            return groupings['inbound']


class JourneyPatternSection(object):
    """A collection of JourneyPatternStopUsages, in order."""
    def __init__(self, element, stops):
        self.id = element.get('id')
        self.timinglinks = [
            JourneyPatternTimingLink(timinglink_element, stops)
            for timinglink_element in element
        ]


class JourneyPatternStopUsage(object):
    """Either a 'From' or 'To' element in TransXChange."""
    def __init__(self, element, stops):
        self.activity = element.find('txc:Activity', NS)
        if self.activity is not None:
            self.activity = self.activity.text
        self.sequencenumber = element.get('SequenceNumber')
        if self.sequencenumber is not None:
            self.sequencenumber = int(self.sequencenumber)
        self.stop = stops.get(element.find('txc:StopPointRef', NS).text)
        if self.stop is None:
            self.stop = Stop(element)
        self.timingstatus = element.find('txc:TimingStatus', NS).text

        waittime_element = element.find('txc:WaitTime', NS)
        if waittime_element is not None:
            self.waittime = parse_duration(waittime_element.text)

        self.row = None
        self.parent = None


class JourneyPatternTimingLink(object):
    def __init__(self, element, stops):
        self.origin = JourneyPatternStopUsage(element.find('txc:From', NS), stops)
        self.destination = JourneyPatternStopUsage(element.find('txc:To', NS), stops)
        self.origin.parent = self.destination.parent = self
        self.runtime = parse_duration(element.find('txc:RunTime', NS).text)
        self.id = element.get('id')
        if self.id:
            if self.id.startswith('JPL_8-229-B-y11-1-'):
                self.replace_atco_code('4200F063300', '4200F147412', stops)
            elif self.id.startswith('JPL_18-X52-_-y08-1-2-R'):
                self.replace_atco_code('3390S9', '3390S10', stops)
            elif self.id.startswith('JPL_4-X52-_-y11-1-'):
                self.replace_atco_code('3390BB01', '3390S10', stops)

    def replace_atco_code(self, code, replacement, stops):
        if self.origin.stop.atco_code == code:
            self.origin.stop.atco_code = replacement
            stops[replacement] = stops[code]
        if self.destination.stop.atco_code == code:
            self.destination.stop.atco_code = replacement
            stops[replacement] = stops[code]


def get_deadruns(journey_element):
    """Given a VehicleJourney element, return a tuple."""
    start_element = journey_element.find('txc:StartDeadRun', NS)
    end_element = journey_element.find('txc:EndDeadRun', NS)
    return (get_deadrun_ref(start_element), get_deadrun_ref(end_element))


def get_deadrun_ref(deadrun_element):
    """Given a StartDeadRun or EndDeadRun element,
    return the ID of a JourneyPetternTimingLink.
    """
    if deadrun_element is not None:
        return deadrun_element.find('txc:ShortWorking/txc:JourneyPatternTimingLinkRef', NS).text


class VehicleJourney(object):
    """A journey represents a scheduled journey that happens at most once per
    day. A sort of "instance" of a JourneyPattern, made distinct by having its
    own start time (and possibly operating profile and dead run).
    """
    operating_profile = None

    def __init__(self, element, journeypatterns, servicedorgs):

        self.code = element.find('txc:VehicleJourneyCode', NS).text
        self.private_code = element.find('txc:PrivateCode', NS)
        if self.private_code is not None:
            self.private_code = self.private_code.text

        journeypatternref_element = element.find('txc:JourneyPatternRef', NS)
        if journeypatternref_element is not None:
            self.journeypattern = journeypatterns.get(journeypatternref_element.text)
        else:
            # Journey has no direct reference to a JourneyPattern.
            # Instead, it has a reference to another journey...
            self.journeyref = element.find('txc:VehicleJourneyRef', NS).text

        operatingprofile_element = element.find('txc:OperatingProfile', NS)
        if operatingprofile_element is not None:
            self.operating_profile = OperatingProfile(operatingprofile_element, servicedorgs)

        self.departure_time = datetime.datetime.strptime(
            element.find('txc:DepartureTime', NS).text, '%H:%M:%S'
        ).time()

        service_ref = element.find('txc:ServiceRef', NS)
        if service_ref is not None and service_ref.text == 'HIBO809':
            if self.departure_time == datetime.time(9, 5) or self.departure_time == datetime.time(10, 10):
                self.departure_time = datetime.time(10, 0)

        if self.code == 'VJ_36-148-_-y10-1-2-T0' and self.departure_time == datetime.time(15, 2):
            self.departure_time = datetime.time(7, 50)
        elif self.code == 'VJ_36-148-_-y10-1-1-T0' and self.departure_time == datetime.time(7, 50):
            self.departure_time = datetime.time(15, 10)
        elif self.code == 'VJ_43-40-_-y10-1-19-T0' and self.departure_time == datetime.time(8, 0):
            self.departure_time = datetime.time(7, 55)

        self.operator = element.find('txc:OperatorRef', NS)
        if self.operator is not None:
            self.operator = self.operator.text

        sequencenumber = element.get('SequenceNumber')
        self.sequencenumber = sequencenumber and int(sequencenumber)

        self.start_deadrun, self.end_deadrun = get_deadruns(element)

        note_elements = element.findall('txc:Note', NS)
        if note_elements is not None:
            self.notes = {
                note_element.find('txc:NoteCode', NS).text: note_element.find('txc:NoteText', NS).text
                for note_element in note_elements
            }

    def get_times(self):
        stopusage = self.journeypattern.sections[0].timinglinks[0].origin
        time = self.departure_time
        deadrun = self.start_deadrun is not None
        if not deadrun:
            yield(stopusage, time)

        for section in self.journeypattern.sections:
            for timinglink in section.timinglinks:
                stopusage = timinglink.destination
                if hasattr(timinglink.origin, 'waittime'):
                    time = add_time(time, timinglink.origin.waittime)

                time = add_time(time, timinglink.runtime)

                if deadrun:
                    if self.start_deadrun == timinglink.id:
                        deadrun = False  # end of dead run
                elif not (self.code.startswith('VJ_45-16A-_-y10-2') and stopusage.timingstatus == 'OTH'):
                    yield(stopusage, time)

                if self.end_deadrun == timinglink.id:
                    deadrun = True  # start of dead run
                if hasattr(stopusage, 'waittime'):
                    time = add_time(time, stopusage.waittime)

    def add_times(self):
        row_length = len(self.journeypattern.grouping.rows[0].times)

        for stopusage, time in self.get_times():
            stopusage.row.times.append(time)

        rows = self.journeypattern.grouping.rows
        for row in rows:
            while len(row.times) <= row_length:
                row.times.append('')

    def cmp(self, x, y):
        """Compare two journeys"""
        x_time = x.departure_time
        y_time = y.departure_time
        if (
            x.journeypattern.sections[0].timinglinks[0].origin.stop.atco_code
            != y.journeypattern.sections[0].timinglinks[0].origin.stop.atco_code
        ):
            times = {part.stop.atco_code: time for part, time in x.get_times()}
            for part, time in y.get_times():
                if part.stop.atco_code in times:
                    if time >= y.departure_time and times[part.stop.atco_code] >= x.departure_time:
                        x_time = times[part.stop.atco_code]
                        y_time = time
                    break
        if x_time > y_time:
            return 1
        if x_time < y_time:
            return -1
        return 0

    def get_order(self):
        if self.sequencenumber is not None:
            return self.sequencenumber
        return cmp_to_key(self.cmp)(self)

    def should_show(self, date, timetable=None):
        if not date:
            return True
        if self.code.startswith('VJ_34-A1-_-y10-1') and self.departure_time == datetime.time(14, 39):
            return False
        if self.code.startswith('VJ_39-20-_-y10-2-') and date < datetime.date(2018, 5, 27):
            # 20 - Weston-super-Mare - Burnham-on-Sea
            if hasattr(self.operating_profile, 'nonoperation_days'):
                for daterange in self.operating_profile.nonoperation_days:
                    if daterange.start == datetime.date(2018, 9, 3) and daterange.end == datetime.date(2500, 1, 1):
                        return False
        if not self.operating_profile:
            return timetable and timetable.operating_profile.should_show(date)
        if timetable and timetable.service_code == 'PKBO301':
            if hasattr(self, 'departure_time') and self.departure_time > datetime.time(19, 0):
                return False
        return self.operating_profile.should_show(date)


class ServicedOrganisation(object):
    def __init__(self, element):
        self.code = element.find('txc:OrganisationCode', NS).text
        name_element = element.find('txc:Name', NS)
        if name_element is not None:
            self.name = name_element.text

        working_days_element = element.find('txc:WorkingDays', NS)
        if working_days_element is not None:
            self.working_days = [DateRange(e) for e in working_days_element]
        else:
            self.working_days = []

        holidays_element = element.find('txc:Holidays', NS)
        if holidays_element is not None:
            self.holidays = [DateRange(e) for e in holidays_element]
        else:
            self.holidays = []


class ServicedOrganisationDayType(object):
    def __init__(self, element, servicedorgs):
        self.nonoperation_holidays = None
        self.nonoperation_workingdays = None
        self.operation_holidays = None
        self.operation_workingdays = None

        # Days of non-operation:
        noop_element = element.find('txc:DaysOfNonOperation', NS)
        if noop_element is not None:
            noop_hols_element = noop_element.find('txc:Holidays/txc:ServicedOrganisationRef', NS)
            noop_workingdays_element = noop_element.find('txc:WorkingDays/txc:ServicedOrganisationRef', NS)

            if noop_hols_element is not None:
                self.nonoperation_holidays = servicedorgs[noop_hols_element.text]

            if noop_workingdays_element is not None:
                self.nonoperation_workingdays = servicedorgs[noop_workingdays_element.text]

        # Days of operation:
        op_element = element.find('txc:DaysOfOperation', NS)
        if op_element is not None:
            op_hols_element = op_element.find('txc:Holidays/txc:ServicedOrganisationRef', NS)
            op_workingdays_element = op_element.find('txc:WorkingDays/txc:ServicedOrganisationRef', NS)

            if op_hols_element is not None:
                self.operation_holidays = servicedorgs[op_hols_element.text]

            if op_workingdays_element is not None:
                self.operation_workingdays = servicedorgs[op_workingdays_element.text]


class DayOfWeek(object):
    def __init__(self, day):
        if isinstance(day, int):
            self.day = day
        else:
            self.day = WEEKDAYS[day]

    def __eq__(self, other):
        if type(other) == int:
            return self.day == other
        return self.day == other.day

    def __repr__(self):
        return calendar.day_name[self.day]


class OperatingProfile(object):
    def __init__(self, element, servicedorgs):
        element = element

        week_days_element = element.find('txc:RegularDayType/txc:DaysOfWeek', NS)
        self.regular_days = []
        if week_days_element is not None:
            for day in [e.tag[33:] for e in week_days_element]:
                if 'To' in day:
                    day_range_bounds = [WEEKDAYS[i] for i in day.split('To')]
                    day_range = range(day_range_bounds[0], day_range_bounds[1] + 1)
                    self.regular_days += [DayOfWeek(i) for i in day_range]
                elif day == 'Weekend':
                    self.regular_days += [DayOfWeek(5), DayOfWeek(6)]
                else:
                    self.regular_days.append(DayOfWeek(day))

        # Special Days:

        special_days_element = element.find('txc:SpecialDaysOperation', NS)

        if special_days_element is not None:
            nonoperation_days_element = special_days_element.find('txc:DaysOfNonOperation', NS)

            if nonoperation_days_element is not None:
                self.nonoperation_days = list(map(DateRange, nonoperation_days_element.findall('txc:DateRange', NS)))

            operation_days_element = special_days_element.find('txc:DaysOfOperation', NS)

            if operation_days_element is not None:
                self.operation_days = list(map(DateRange, operation_days_element.findall('txc:DateRange', NS)))

        # Serviced Organisation:

        servicedorg_days_element = element.find('txc:ServicedOrganisationDayType', NS)

        if servicedorg_days_element is not None:
            self.servicedorganisation = ServicedOrganisationDayType(servicedorg_days_element, servicedorgs)

        # Bank Holidays

        bank_holidays_operation_element = element.find('txc:BankHolidayOperation/txc:DaysOfOperation', NS)
        bank_holidays_nonoperation_element = element.find('txc:BankHolidayOperation/txc:DaysOfNonOperation', NS)
        if bank_holidays_operation_element is not None:
            self.operation_bank_holidays = [e.tag[33:] for e in bank_holidays_operation_element]
        else:
            self.operation_bank_holidays = []

        if bank_holidays_nonoperation_element is not None:
            self.nonoperation_bank_holidays = [e.tag[33:] for e in bank_holidays_nonoperation_element]
        else:
            self.nonoperation_bank_holidays = []

    def should_show(self, date):
        if hasattr(self, 'nonoperation_days'):
            for daterange in self.nonoperation_days:
                if daterange.contains(date):
                    return False

        if hasattr(self, 'operation_days'):
            for daterange in self.operation_days:
                if daterange.contains(date):
                    return True

        if self.regular_days:
            if date.weekday() not in self.regular_days:
                return False
        if date in BANK_HOLIDAYS:
            if 'AllBankHolidays' in self.operation_bank_holidays:
                return True
            if 'AllBankHolidays' in self.nonoperation_bank_holidays:
                return False
            for bank_holiday in BANK_HOLIDAYS[date]:
                if bank_holiday in self.operation_bank_holidays:
                    return True
                if bank_holiday in self.nonoperation_bank_holidays:
                    return False

        if not self.regular_days:
            return False

        if hasattr(self, 'servicedorganisation'):
            org = self.servicedorganisation

            nonoperation_days = (org.nonoperation_workingdays and org.nonoperation_workingdays.working_days or
                                 org.nonoperation_holidays and org.nonoperation_holidays.holidays)
            if nonoperation_days:
                return not any(daterange.contains(date) for daterange in nonoperation_days)

            operation_days = (org.operation_workingdays and org.operation_workingdays.working_days or
                              org.operation_holidays and org.operation_holidays.holidays)
            if operation_days:
                return any(daterange.contains(date) for daterange in operation_days)

        return True


class DateRange(object):
    def __init__(self, element):
        self.start = ciso8601.parse_datetime(element.find('txc:StartDate', NS).text).date()
        self.end = element.find('txc:EndDate', NS)
        if self.end is not None:
            self.end = ciso8601.parse_datetime(self.end.text).date()

    def __str__(self):
        if self.start == self.end:
            return self.start.strftime('%-d %B %Y')
        else:
            return '%s to %s' % (self.start, self.end)

    def contains(self, date):
        return self.start <= date and (not self.end or self.end >= date)


class OperatingPeriod(DateRange):
    def __str__(self):
        if self.start == self.end:
            return self.start.strftime('on %-d %B %Y')
        today = datetime.date.today()
        if self.start > today:
            if self.end is None or self.end.year > today.year + 1:
                return self.start.strftime('from %-d %B %Y')
            if self.start.year == self.end.year:
                if self.start.month == self.end.month:
                    start_format = '%-d'
                else:
                    start_format = '%-d %B'
            else:
                start_format = '%-d %B %Y'
            return 'from %s to %s' % (
                self.start.strftime(start_format), self.end.strftime('%-d %B %Y')
            )
        # The end date is often bogus,
        # but show it if the period seems short enough to be relevant
        if self.end is not None and (self.end - self.start).days < 7:
            return self.end.strftime('until %-d %B %Y')
        return ''


class ColumnFoot(object):
    def __init__(self, notes, span):
        self.notes = notes
        self.span = span


class Timetable(object):
    def __get_journeys(self, journeys_element, servicedorgs):
        journeys = {
            journey.code: journey for journey in (
                VehicleJourney(element, self.journeypatterns, servicedorgs)
                for element in journeys_element
            )
        }

        if self.service_code == '21-584-_-y08-1':  # 584 - Diss - Pulham Market
            journeys['VJ_21-584-_-y08-1-2-T0'].departure_time = datetime.time(9, 20)

        # some journeys did not have a direct reference to a journeypattern,
        # but rather a reference to another journey with a reference to a journeypattern
        for journey in iter(journeys.values()):
            if hasattr(journey, 'journeyref'):
                journey.journeypattern = journeys[journey.journeyref].journeypattern

        return (journey for journey in journeys.values() if journey.journeypattern)

    def date_options(self):
        start_date = min(self.date, datetime.date.today())
        end_date = start_date + datetime.timedelta(weeks=4)
        while start_date <= end_date:
            yield start_date
            start_date += datetime.timedelta(days=1)
        if self.date >= start_date:
            yield self.date

    def set_date(self, date):
        if date and not isinstance(date, datetime.date):
            date = ciso8601.parse_datetime(date).date()

        if hasattr(self, 'date'):
            if date == self.date:
                return
            for grouping in self.groupings:
                for row in grouping.rows:
                    row.times.clear()
                grouping.column_feet.clear()

        self.date = date

        for grouping in self.groupings:
            for journey in grouping.journeys:
                if journey.should_show(self.date, self):
                    journey.add_times()
            grouping.do_heads_and_feet()

    def __init__(self, open_file, date, description=None):
        iterator = ET.iterparse(open_file)

        element = None
        servicedorgs = None

        self.description = description
        routes = {}

        for _, element in iterator:
            tag = element.tag[33:]

            if tag == 'StopPoints':
                self.stops = {
                    stop.find('txc:StopPointRef', NS).text: Stop(stop)
                    for stop in element
                }
                element.clear()
            elif tag == 'Routes':
                routes = {
                    route.get('id'): route.find('txc:Description', NS).text
                    for route in element
                }
                element.clear()
            elif tag == 'RouteSections':
                element.clear()
            elif tag == 'Operators':
                self.operators = element
            elif tag == 'JourneyPatternSections':
                journeypatternsections = {
                    section.id: section for section in (
                        JourneyPatternSection(section, self.stops) for section in element
                    ) if section.timinglinks
                }
                element.clear()
            elif tag == 'ServicedOrganisations':
                servicedorgs = {
                    org.code: org for org in (ServicedOrganisation(org_element) for org_element in element)
                }
            elif tag == 'VehicleJourneys':
                # time calculation begins here:
                try:
                    journeys = self.__get_journeys(element, servicedorgs)
                except AttributeError as e:
                    print(e)
                    return
                element.clear()
            elif tag == 'Service':
                mode_element = element.find('txc:Mode', NS)
                if mode_element is not None:
                    self.mode = mode_element.text
                else:
                    self.mode = ''

                self.operator = element.find('txc:RegisteredOperatorRef', NS)
                if self.operator is not None:
                    self.operator = self.operator.text

                operatingprofile_element = element.find('txc:OperatingProfile', NS)
                if operatingprofile_element is not None:
                    self.operating_profile = OperatingProfile(operatingprofile_element, servicedorgs)

                self.operating_period = OperatingPeriod(element.find('txc:OperatingPeriod', NS))

                self.service_code = element.find('txc:ServiceCode', NS).text

                description_element = element.find('txc:Description', NS)
                if description_element is not None:
                    description = description_element.text
                    if description.isupper():
                        description = titlecase(description)
                    self.description = correct_description(description)

                self.via = None
                if self.description:
                    self.description_parts = list(map(sanitize_description_part, self.description.split(' - ')))
                    if ' via ' in self.description_parts[-1]:
                        self.description_parts[-1], self.via = self.description_parts[-1].split(' via ', 1)
                else:
                    self.description_parts = None

                self.groupings = {
                    'outbound': Grouping('outbound', self),
                    'inbound': Grouping('inbound', self)
                }
                self.journeypatterns = {
                    pattern.id: pattern for pattern in (
                       JourneyPattern(pattern, journeypatternsections, self.groupings, routes)
                       for pattern in element.findall('txc:StandardService/txc:JourneyPattern', NS)
                    ) if pattern.sections
                }
                self.groupings = list(self.groupings.values())

        self.element = element

        self.transxchange_date = max(
            element.attrib['CreationDateTime'], element.attrib['ModificationDateTime']
        )[:10]

        for journey in journeys:
            journey.journeypattern.grouping.journeys.append(journey)

        if journey.private_code and ':' in journey.private_code:
            self.private_code = journey.private_code.split(':', 1)[0]
        else:
            self.private_code = None

        del journeys

        for grouping in self.groupings:
            grouping.journeys.sort(key=VehicleJourney.get_order)

        self.groupings.sort(key=lambda g: g.direction, reverse=True)
        if len(self.groupings) == 2 and all(len(g.journeys) == 1 for g in self.groupings):
            self.groupings.sort(key=Grouping.get_order)

        self.set_date(date)

        if self.service_code == 'MGZO460':
            previous_row = None
            for row in self.groupings[1].rows:
                if row.part.stop.atco_code == '5230AWD72040' and previous_row.times[:2] == ['', '']:
                    previous_row.times[0] = row.times[0]
                    previous_row.times[1] = row.times[1]
                previous_row = row


def abbreviate(grouping, i, in_a_row, difference):
    """Given a Grouping, and a timedelta, modify each row and..."""
    seconds = difference.total_seconds()
    if not seconds or 3600 % seconds and seconds % 3600:  # not a factor or multiple of 1 hour
        return
    cell = Cell(in_a_row + 1, len(grouping.rows), difference)
    cell.min_height = len([row for row in grouping.rows if not row.is_minor()])
    grouping.rows[0].times[i - in_a_row - 2] = cell
    for j in range(i - in_a_row - 1, i - 1):
        grouping.rows[0].times[j] = None
    for j in range(i - in_a_row - 2, i - 1):
        for row in grouping.rows[1:]:
            row.times[j] = None


def timetable_from_filename(path, filename, day):
    """Given a path and filename, join them, and return a Timetable."""
    if filename[-4:] == '.xml':
        with open(os.path.join(path, filename)) as xmlfile:
            return Timetable(xmlfile, day)

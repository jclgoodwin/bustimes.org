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
from django.utils.dateparse import parse_duration
from titlecase import titlecase

NS = {
    'txc': 'http://www.transxchange.org.uk/'
}
# A safe date, far from any daylight savings changes or leap seconds
DUMMY_DATE = datetime.date(2016, 4, 5)
DESCRIPTION_REGEX = re.compile(r'.+,([^ ].+)$')
WEEKDAYS = {day: i for i, day in enumerate(calendar.day_name)}
BANK_HOLIDAYS = {
    datetime.date(2016, 12, 26): ('BoxingDay',),
    datetime.date(2017, 4, 14): ('GoodFriday',),
    datetime.date(2017, 4, 17): ('EasterMonday', 'HolidayMondays'),
    # datetime.date(2017, 5, 1): ('MayDay', 'HolidayMondays'),
    datetime.date(2017, 5, 29): ('SpringBank', 'HolidayMondays'),
    # datetime.date(2017, 8, 7): ('AugustBankHolidayScotland',),
    # datetime.date(2017, 8, 28): ('LateSummerBankHolidayNotScotland', 'HolidayMondays'),
    # datetime.date(2017, 12, 24): ('ChristmasEve',),
    # datetime.date(2017, 12, 25): ('ChristmasDay', 'ChristmasDayHoliday'),
    # datetime.date(2017, 12, 26): ('BoxingDay', 'BoxingDayHoliday'),
    # datetime.date(2017, 12, 31): ('NewYearsEve',),
    # datetime.date(2018, 1, 1): ('NewYearsDay', 'NewYearsDayHoliday', 'HolidayMondays'),
    # datetime.date(2018, 3, 30): ('GoodFriday',),
    # datetime.date(2018, 4, 2): ('EasterMonday', 'HolidayMondays'),
    # datetime.date(2018, 5, 7): ('MayDay', 'HolidayMondays'),
    datetime.date(2018, 5, 28): ('SpringBank', 'HolidayMondays'),
    datetime.date(2018, 8, 6): ('AugustBankHolidayScotland',),
    datetime.date(2018, 8, 27): ('LateSummerBankHolidayNotScotland',),
    datetime.date(2018, 12, 24): ('ChristmasEve',),
    datetime.date(2018, 12, 25): ('ChristmasDay', 'ChristmasDayHoliday'),
    datetime.date(2018, 12, 26): ('BoxingDay', 'BoxingDayHoliday',),
    datetime.date(2018, 12, 31): ('NewYearsEve',),
    datetime.date(2019, 1, 1): ('NewYearsDay', 'NewYearsDayHoliday'),
    datetime.date(2019, 1, 2): ('Jan2ndScotland',),
    datetime.date(2019, 4, 19): ('GoodFriday',),
    datetime.date(2019, 4, 22): ('EasterMonday', 'HolidayMondays'),  # not in Scotland
    datetime.date(2019, 5, 6): ('MayDay', 'HolidayMondays'),
    datetime.date(2019, 5, 27): ('SpringBank', 'HolidayMondays'),
    datetime.date(2019, 8, 5): ('AugustBankHolidayScotland',),
    datetime.date(2019, 8, 26): ('LateSummerBankHolidayNotScotland', 'HolidayMondays'),
    datetime.date(2019, 12, 2): ('StAndrewsDay',),
    datetime.date(2019, 12, 24): ('ChristmasEve',),  # Not actually a bank holiday?
    datetime.date(2019, 12, 25): ('ChristmasDay',),
    datetime.date(2019, 12, 26): ('BoxingDay',),
    datetime.date(2019, 12, 31): ('NewYearsEve',),  # Not actually a bank holiday?
}


def not_scotland(bank_holiday):
    if bank_holiday.endswith('NotScotland'):
        return True
    if bank_holiday == 'EasterMonday':
        return True
    return False


def only_scotland(bank_holiday):
    if not_scotland(bank_holiday):
        return False
    if bank_holiday.endswith('Scotland'):
        return True
    if bank_holiday == 'StAndrewsDay':
        return True
    return False


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
            ('Greenstead Green', 'Greensted Green'),
            ('Tinagel', 'Tintagel'),
            ('Plymouh City Cerntre', 'Plymouth City Centre'),
            ('Winterbourn', 'Winterbourne'),
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
        if element:
            self.atco_code = element.find('txc:StopPointRef', NS)
            if self.atco_code is None:
                self.atco_code = element.find('txc:AtcoCode', NS)
            if self.atco_code is not None:
                self.atco_code = self.atco_code.text or ''
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


class JourneyPattern(object):
    """A collection of JourneyPatternSections, in order."""
    def __init__(self, element, sections):
        self.id = element.attrib.get('id')
        # self.journeys = []
        self.sections = [
            sections[section_element.text]
            for section_element in element.findall('txc:JourneyPatternSectionRefs', NS)
            if section_element.text in sections
        ]

        self.direction = element.find('txc:Direction', NS)

        if self.direction is not None:
            self.direction = self.direction.text

    def get_timinglinks(self):
        for section in self.sections:
            for timinglink in section.timinglinks:
                yield timinglink


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

        # for Ellenvale Coaches
        if self.stop.atco_code == '090002492728':
            self.activity = 'pickUpAndSetDown'

        self.timingstatus = element.find('txc:TimingStatus', NS).text

        self.wait_time = element.find('txc:WaitTime', NS)
        if self.wait_time is not None:
            self.wait_time = parse_duration(self.wait_time.text)
            if self.wait_time.total_seconds() > 10000:
                print(self.wait_time)
                self.wait_time = None

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
            if self.id.startswith('JPL_21-9-A-y08-1'):  # Carters Coaches North Elmham stop
                self.replace_atco_code('2900E074', '2900E0714', stops)
            elif self.id.startswith('JPL_8-229-B-y11-1-'):  # Ensignbus Snitterfield
                self.replace_atco_code('4200F063300', '4200F147412', stops)
            elif self.id.startswith('JPL_18-X52-_-y08-1-2-R'):  # Notts & Derby Alton Towers
                self.replace_atco_code('3390S9', '3390S10', stops)
            elif self.id.startswith('JPL_4-X52-_-y11-1-'):  # Notts & Derby Alton Towers
                self.replace_atco_code('3390BB01', '3390S10', stops)
            elif self.id.startswith('JPTL'):
                if self.origin.sequencenumber == 1 or self.origin.sequencenumber == 66:
                    # x1-ruthin-chester-via-mold
                    self.replace_atco_code('0610CH19065', '0610CH2395', stops)

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
    journey_pattern = None
    journey_ref = None

    def __str__(self):
        return str(self.departure_time)

    def __init__(self, element, journey_patterns, serviced_organisations):
        self.code = element.find('txc:VehicleJourneyCode', NS).text
        self.private_code = element.find('txc:PrivateCode', NS)
        if self.private_code is not None:
            self.private_code = self.private_code.text

        journeypatternref_element = element.find('txc:JourneyPatternRef', NS)
        if journeypatternref_element is not None:
            self.journey_pattern = journey_patterns.get(journeypatternref_element.text)
        else:
            # Journey has no direct reference to a JourneyPattern.
            # Instead, it has a reference to another journey...
            self.journey_ref = element.find('txc:VehicleJourneyRef', NS).text

        operatingprofile_element = element.find('txc:OperatingProfile', NS)
        if operatingprofile_element is not None:
            self.operating_profile = OperatingProfile(operatingprofile_element, serviced_organisations)

        self.departure_time = datetime.datetime.strptime(
            element.find('txc:DepartureTime', NS).text, '%H:%M:%S'
        ).time()

        self.start_deadrun, self.end_deadrun = get_deadruns(element)

        self.operator = element.find('txc:OperatorRef', NS)
        if self.operator is not None:
            self.operator = self.operator.text

        sequencenumber = element.get('SequenceNumber')
        self.sequencenumber = sequencenumber and int(sequencenumber)

        note_elements = element.findall('txc:Note', NS)
        if note_elements is not None:
            self.notes = {
                note_element.find('txc:NoteCode', NS).text: note_element.find('txc:NoteText', NS).text
                for note_element in note_elements
            }

    def skip_stopusage(self, stopusage, time):
        # Ebley Coaches
        if self.code.startswith('VJ_45-16A-_-y10-') and stopusage.timingstatus == 'OTH':
            return True

        # Shiel Buses ferry terminal
        if stopusage.stop.atco_code == '670088829' and time.hour == 11:
            return True

        # Sanders 45, 45A Briston loop
        if '-45-_-' in self.code or '-45A-_-' in self.code:
            if stopusage.stop.atco_code in {'2900B511', '2900B517', '2900B5119', '2900B5120'}:
                return True

        # Sanders 24 Salle
        if '-24-_-' in self.code and stopusage.stop.atco_code in {'2900S031', '2900S032'}:
            return True

        return False

    def get_times(self):
        stopusage = None
        time = self.departure_time
        deadrun = self.start_deadrun is not None
        deadrun_next = False

        for timinglink in self.journey_pattern.get_timinglinks():
            if stopusage and stopusage.wait_time:
                wait_time = stopusage.wait_time
            else:
                wait_time = None

            stopusage = timinglink.origin

            if deadrun and self.start_deadrun == timinglink.id:
                deadrun = False  # end of dead run

            if not deadrun and not self.skip_stopusage(stopusage, time):
                # Simonds Diss to Beccles
                if stopusage.stop.atco_code == '2900R241' and timinglink.origin.stop.atco_code == '2900R2417':
                    stopusage.stop = Stop(None)
                    stopusage.stop.atco_code = None
                    stopusage.stop.locality = 'Harleston'
                    stopusage.stop.common_name = 'Redenhall Rd/Station Rd'

                if stopusage.wait_time or wait_time:
                    next_time = add_time(time, stopusage.wait_time or wait_time)
                    yield Cell(stopusage, time, next_time)
                    time = next_time
                else:
                    yield Cell(stopusage, time, time)

            if timinglink.runtime:
                time = add_time(time, timinglink.runtime)

            if deadrun_next:
                deadrun = True
                deadrun_next = False
            elif self.end_deadrun == timinglink.id:
                deadrun_next = True  # start of dead run

            stopusage = timinglink.destination

        if not deadrun:
            yield Cell(timinglink.destination, time, time)

    def add_times(self):
        # width before adding this journey column
        initial_width = len(self.journey_pattern.grouping.rows[0].times)

        for cell in self.get_times():
            cell.stopusage.row.times.append(cell)
        cell.last = True

        rows = self.journey_pattern.grouping.rows

        previous_row = None
        for row in rows:

            if previous_row:
                if len(row.times) > initial_width + 1:
                    if row.part.stop.atco_code == previous_row.part.stop.atco_code:
                        assert previous_row.times[-1] == ''
                        previous_row.times[-1] = row.times[-2]
                        row.times = row.times[:-2] + row.times[-1:]

                if len(previous_row.times) > initial_width + 1:
                    if len(row.times) == initial_width:
                        row.times.append(previous_row.times.pop())
                    else:
                        index = rows.index(previous_row) - 1
                        while index >= 0:
                            previous_previous_row = rows[index]
                            if previous_previous_row.part.stop.atco_code == previous_row.part.stop.atco_code:
                                assert previous_previous_row.times[-1] == ''
                                previous_previous_row.times[-1] = previous_row.times[-2]
                                previous_row.times = previous_row.times[:-2] + previous_row.times[-1:]
                                break
                            index -= 1

                assert len(previous_row.times) == initial_width + 1

            if len(row.times) == initial_width:
                row.times.append('')

            previous_row = row

    def cmp(x, y):
        """Compare two journeys"""
        if x.sequencenumber is not None and y.sequencenumber is not None:
            if x.sequencenumber > y.sequencenumber:
                return 1
            if x.sequencenumber < y.sequencenumber:
                return -1
            return 0
        x_time = x.departure_time
        y_time = y.departure_time
        if (
            x.journey_pattern.sections[0].timinglinks[0].origin.stop.atco_code
            != y.journey_pattern.sections[0].timinglinks[0].origin.stop.atco_code
        ):
            times = {cell.stopusage.stop.atco_code: cell.arrival_time for cell in x.get_times()}
            for cell in y.get_times():
                if cell.stopusage.stop.atco_code in times:
                    if cell.arrival_time >= y.departure_time:
                        if times[cell.stopusage.stop.atco_code] >= x.departure_time:
                            x_time = times[cell.stopusage.stop.atco_code]
                            y_time = cell.arrival_time
                    break
        if x_time > y_time:
            return 1
        if x_time < y_time:
            return -1
        return 0

    def should_show(self, date, transxchange=None):
        if not date:
            return True
        if transxchange and transxchange.service:
            region_id = transxchange.service.region_id
            if transxchange.service.service_code == 'twm_5-501-A-y11':
                if self.departure_time == datetime.time(14, 15):
                    self.departure_time = datetime.time(14, 10)
                elif self.departure_time == datetime.time(15, 18):
                    self.departure_time = datetime.time(15, 48)
                elif (self.departure_time == datetime.time(8, 33) or self.departure_time == datetime.time(15, 5)
                      or self.departure_time == datetime.time(8, 20)):
                    return False
        else:
            region_id = None
        if not self.operating_profile:
            return transxchange and transxchange.operating_profile.should_show(date, region_id)
        return self.operating_profile.should_show(date, region_id)


class ServicedOrganisation(object):
    def __init__(self, element):
        self.code = element.find('txc:OrganisationCode', NS).text
        self.name = element.find('txc:Name', NS)
        if self.name is not None:
            self.name = self.name.text

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

        if self.name == 'Devon School Holidays':
            self.holidays.append(DateRange(ET.fromstring("""
                <DateRange xmlns="http://www.transxchange.org.uk/">
                    <StartDate>2019-07-26</StartDate>
                    <EndDate>2019-08-30</EndDate>
                </DateRange>
            """)))


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
    servicedorganisation = None
    nonoperation_days = ()
    operation_days = ()

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
                elif day[:3] == 'Not':
                    print(day)
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

    def should_show(self, date, region_id=None):
        for daterange in self.nonoperation_days:
            if daterange.contains(date):
                return False

        for daterange in self.operation_days:
            if daterange.contains(date):
                return True

        if date in BANK_HOLIDAYS:
            if not (
                region_id == 'S' and any(not_scotland(bank_holiday) for bank_holiday in BANK_HOLIDAYS[date])
                or region_id != 'S' and any(only_scotland(bank_holiday) for bank_holiday in BANK_HOLIDAYS[date])
            ):
                if 'AllBankHolidays' in self.operation_bank_holidays:
                    return True
                if 'AllBankHolidays' in self.nonoperation_bank_holidays:
                    return False
            for bank_holiday in BANK_HOLIDAYS[date]:
                if bank_holiday in self.operation_bank_holidays:
                    return True
                if bank_holiday in self.nonoperation_bank_holidays:
                    return False

        if self.regular_days:
            if date.weekday() not in self.regular_days:
                return False

        if not self.regular_days:
            return False

        if self.servicedorganisation:
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
            if self.end and (self.end - self.start).days < 14:
                start_format = '%-d'
                if self.start.month != self.end.month:
                    start_format += ' %B'
                if self.start.year != self.end.year:
                    start_format += ' %Y'
                return 'from {} to {}'.format(
                    self.start.strftime(start_format),
                    self.end.strftime('%-d %B %Y')
                )
            return self.start.strftime('from %-d %B %Y')
        # The end date is often bogus,
        # but show it if the period seems short enough to be relevant
        if self.end and (self.end - self.start).days < 7:
            return self.end.strftime('until %-d %B %Y')
        return ''


class TransXChange(object):
    description = None
    description_parts = None
    via = None
    service = None

    def __get_journeys(self, journeys_element, serviced_organisations):
        journeys = {
            journey.code: journey for journey in (
                VehicleJourney(element, self.journey_patterns, serviced_organisations)
                for element in journeys_element
            )
        }

        # Some Journeys do not have a direct reference to a JourneyPattern,
        # but rather a reference to another Journey which has a reference to a JourneyPattern
        for journey in iter(journeys.values()):
            if journey.journey_ref and not journey.journey_pattern:
                journey.journey_pattern = journeys[journey.journey_ref].journey_pattern

        return [journey for journey in journeys.values() if journey.journey_pattern]

    def set_description(self, description):
        if description.isupper():
            description = titlecase(description)
        self.description = correct_description(description)

        self.via = None
        self.description_parts = list(map(sanitize_description_part, self.description.split(' - ')))
        if ' via ' in self.description_parts[-1]:
            self.description_parts[-1], self.via = self.description_parts[-1].split(' via ', 1)

    def __init__(self, open_file):
        iterator = ET.iterparse(open_file)

        # element = None
        serviced_organisations = None

        for _, element in iterator:
            tag = element.tag[33:]

            if tag == 'StopPoints':
                stops = (Stop(stop) for stop in element)
                self.stops = {stop.atco_code: stop for stop in stops}
                element.clear()
            elif tag == 'Routes':
                # routes = {
                #     route.get('id'): route.find('txc:Description', NS).text
                #     for route in element
                # }
                element.clear()
            elif tag == 'RouteSections':
                element.clear()
            elif tag == 'Operators':
                self.operators = element
            elif tag == 'JourneyPatternSections':
                journey_pattern_sections = {
                    section.id: section for section in (
                        JourneyPatternSection(section, self.stops) for section in element
                    ) if section.timinglinks
                }
                element.clear()
            elif tag == 'ServicedOrganisations':
                serviced_organisations = (ServicedOrganisation(child) for child in element)
                serviced_organisations = {
                    organisation.code: organisation for organisation in serviced_organisations
                }
            elif tag == 'VehicleJourneys':
                try:
                    self.journeys = self.__get_journeys(element, serviced_organisations)
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
                    self.operating_profile = OperatingProfile(operatingprofile_element, serviced_organisations)

                self.operating_period = OperatingPeriod(element.find('txc:OperatingPeriod', NS))

                self.service_code = element.find('txc:ServiceCode', NS).text

                description_element = element.find('txc:Description', NS)
                if description_element is not None:
                    self.set_description(description_element.text)

                self.journey_patterns = {
                    journey_pattern.id: journey_pattern for journey_pattern in (
                       JourneyPattern(journey_pattern, journey_pattern_sections)
                       for journey_pattern in element.findall('txc:StandardService/txc:JourneyPattern', NS)
                    ) if journey_pattern.sections
                }

        self.element = element

        self.transxchange_date = max(
            element.attrib['CreationDateTime'], element.attrib['ModificationDateTime']
        )[:10]


class Row(object):
    """A row in a grouping in a timetable.
    Each row is associated with a Stop, and a list of times.
    """
    def __init__(self, part):
        self.part = part
        self.stop = part.stop
        part.row = self
        self.times = []

    def timing_status(self):
        return self.part.timingstatus

    def is_minor(self):
        return self.part.timingstatus == 'OTH' or self.part.timingstatus == 'TIP'

    def __repr__(self):
        return str(self.stop)


class Cell(object):
    last = False

    def __init__(self, stopusage, arrival_time, departure_time):
        self.stopusage = stopusage
        self.arrival_time = arrival_time
        self.departure_time = departure_time
        self.wait_time = arrival_time and departure_time and arrival_time != departure_time

    def __str__(self):
        return self.arrival_time.strftime('%H:%M')

    def __eq__(self, other):
        if type(other) == datetime.time:
            return self.arrival_time == other or self.departure_time == other
        return self.arrival_time == other.arrival_time and self.departure_time == other.departure_time


class Repetition(object):
    """Represents a special cell in a timetable, spanning multiple rows and columns,
    with some text like 'then every 5 minutes until'.
    """
    def __init__(self, colspan, rowspan, duration):
        self.colspan = colspan
        self.rowspan = self.min_height = rowspan
        self.duration = duration

    def __str__(self):
        # cleverly add non-breaking spaces if there aren't many rows
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
    """
    differ = difflib.Differ(charjunk=lambda _: True)

    def __init__(self, direction, parent):
        self.direction = direction
        self.parent = parent
        self.description_parts = None
        self.heads = []
        self.column_feet = {}
        self.journey_patterns = []
        self.journeys = []
        self.rows = []

    def add_journey_pattern(self, journey_patttern):
        # the rows traversed by this journey pattern
        rows = []

        for timinglink in journey_patttern.get_timinglinks():
            rows.append(Row(timinglink.origin))
        rows.append(Row(timinglink.destination))

        if not rows:
            return

        # this grouping's current rows (an amalgamation from any previously handled journey patterns)
        previous_list = [row.part.stop.atco_code for row in self.rows]

        # this journey pattern again
        current_list = [row.part.stop.atco_code for row in rows]
        diff = self.differ.compare(previous_list, current_list)

        i = 0
        first = True
        for row in rows:
            if i < len(self.rows):
                existing_row = self.rows[i]
            else:
                existing_row = None
            instruction = next(diff)
            while instruction[0] in '-?':
                if instruction[0] == '-':
                    i += 1
                    if i < len(self.rows):
                        existing_row = self.rows[i]
                    else:
                        existing_row = None
                instruction = next(diff)

            assert instruction[2:] == row.part.stop.atco_code

            if instruction[0] == '+':
                if not existing_row:
                    self.rows.append(row)
                else:
                    self.rows = self.rows[:i] + [row] + self.rows[i:]
                existing_row = row
            else:
                assert instruction[2:] == existing_row.part.stop.atco_code
                row.part.row = existing_row

            if first:
                existing_row.first = True  # row is the first row of this pattern
                first = False
            i += 1

        existing_row.last = True  # row is the last row of this pattern

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
        prev_journey = None
        in_a_row = 0
        prev_difference = None
        difference = None

        for i, journey in enumerate(self.journeys):
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
                if prev_journey.service != journey.service:
                    if self.heads:
                        self.heads.append(ColumnHead(prev_journey.service, i - sum(head.span for head in self.heads)))
                    else:
                        self.heads.append(ColumnHead(prev_journey.service, i))
                if prev_journey.notes != journey.notes:
                    if in_a_row > 1:
                        abbreviate(self, i, in_a_row - 1, prev_difference)
                    in_a_row = 0
                elif prev_journey.journey_pattern.id == journey.journey_pattern.id:
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

        if self.heads or (prev_journey and prev_journey.service != self.parent.service):
            self.heads.append(ColumnHead(prev_journey.service,
                                         len(self.journeys) - sum(head.span for head in self.heads)))

        if in_a_row > 1:
            abbreviate(self, len(self.journeys), in_a_row - 1, prev_difference)
        for row in self.rows:
            # remove 'None' cells created during the abbreviation process
            # (actual empty cells will contain an empty string '')
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

        if self.parent.service:
            return getattr(self.parent.service, self.direction + '_description')

        return self.direction.capitalize()


class ColumnHead(object):
    def __init__(self, service, span):
        self.service = service
        self.span = span


class ColumnFoot(object):
    def __init__(self, notes, span):
        self.notes = notes
        self.span = span


class Timetable(object):
    service = None
#     description = None
    description_parts = None

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
                grouping.heads.clear()
                grouping.column_feet.clear()
                grouping.journeys.clear()

        self.date = date

        for transxchange in self.transxchanges:
            if not date or transxchange.operating_period.contains(date):
                for journey in transxchange.journeys:
                    if journey.should_show(date, transxchange):
                        journey.journey_pattern.grouping.journeys.append(journey)
                        journey.service = transxchange.service

        for grouping in self.groupings:
            grouping.journeys.sort(key=cmp_to_key(VehicleJourney.cmp))
            for journey in grouping.journeys:
                journey.add_times()
            for row in grouping.rows:
                row.has_waittimes = any(type(cell) is Cell and cell.wait_time for cell in row.times)
            grouping.do_heads_and_feet()

        if all(len(g.journeys) for g in self.groupings):
            self.groupings.sort(key=Grouping.get_order)

    def has_set_down_only(self):
        for grouping in self.groupings:
            for row in grouping.rows[:-1]:
                for cell in row.times:
                    if type(cell) is Cell and not cell.last and cell.stopusage.activity == 'setDown':
                        return True

    def __init__(self, open_files, date=None, service=None):
        self.service = service

        groupings = {
            'outbound': Grouping('outbound', self),
            'inbound': Grouping('inbound', self)
        }

        if type(open_files) is list:
            self.transxchanges = [TransXChange(pair[1]) for pair in open_files]
            self.service = open_files[0][0]
        else:
            self.transxchanges = [TransXChange(open_files)]

        for i, transxchange in enumerate(self.transxchanges):
            if i:
                transxchange.service = open_files[i][0]
            else:
                transxchange.service = self.service
            for journey_pattern in transxchange.journey_patterns.values():
                if journey_pattern.direction == 'inbound':
                    grouping = groupings['inbound']
                else:
                    grouping = groupings['outbound']
                grouping.add_journey_pattern(journey_pattern)
                journey_pattern.grouping = grouping
            self.description_parts = transxchange.description_parts
            self.via = transxchange.via

        self.groupings = list(groupings.values())

        self.set_date(date)


def abbreviate(grouping, i, in_a_row, difference):
    """Given a Grouping, and a timedelta, modify each row and..."""
    seconds = difference.total_seconds()
    if not seconds or (seconds != 3600 and seconds > 1800):  # neither hourly nor more than every 30 minutes
        return
    repetition = Repetition(in_a_row + 1, sum(2 if row.has_waittimes else 1 for row in grouping.rows), difference)
    repetition.min_height = sum(2 if row.has_waittimes else 1 for row in grouping.rows if not row.is_minor())
    grouping.rows[0].times[i - in_a_row - 2] = repetition
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

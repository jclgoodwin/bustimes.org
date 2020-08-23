"""Represent TransXChange concepts, and generate a matrix timetable from
TransXChange documents
"""
import re
import xml.etree.cElementTree as ET
import calendar
import datetime
import ciso8601
import logging
from psycopg2.extras import DateRange as PDateRange
from django.utils.text import slugify
from django.utils.dateparse import parse_duration
from chardet.universaldetector import UniversalDetector
from titlecase import titlecase


logger = logging.getLogger(__name__)


NS = {
    'txc': 'http://www.transxchange.org.uk/'
}
# A safe date, far from any daylight savings changes or leap seconds
DESCRIPTION_REGEX = re.compile(r'.+,([^ ].+)$')
WEEKDAYS = {day: i for i, day in enumerate(calendar.day_name)}


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
            ('Winterbourn ', 'Winterbourne'),
            ('Exetedr', 'Exeter'),
            ('- ', ' - '),
            (' -', ' - '),
            ('  ', ' '),
    ):
        description = description.replace(old, new)
    return description


class Stop:
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


class JourneyPattern:
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


class JourneyPatternSection:
    """A collection of JourneyPatternStopUsages, in order."""
    def __init__(self, element, stops):
        self.id = element.get('id')
        self.timinglinks = [
            JourneyPatternTimingLink(timinglink_element, stops)
            for timinglink_element in element
        ]


class JourneyPatternStopUsage:
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

        self.timingstatus = element.find('txc:TimingStatus', NS)
        if self.timingstatus is not None:
            self.timingstatus = self.timingstatus.text

        self.wait_time = element.find('txc:WaitTime', NS)
        if self.wait_time is not None:
            self.wait_time = parse_duration(self.wait_time.text)
            if self.wait_time.total_seconds() > 10000:
                # bad data detected
                print(self.wait_time)
                self.wait_time = None

        self.row = None
        self.parent = None


class JourneyPatternTimingLink:
    def __init__(self, element, stops):
        self.origin = JourneyPatternStopUsage(element.find('txc:From', NS), stops)
        self.destination = JourneyPatternStopUsage(element.find('txc:To', NS), stops)
        self.origin.parent = self.destination.parent = self
        self.runtime = parse_duration(element.find('txc:RunTime', NS).text)
        self.id = element.get('id')


def get_deadruns(journey_element):
    """Given a VehicleJourney element, return a tuple."""
    start_element = journey_element.find('txc:StartDeadRun', NS)
    end_element = journey_element.find('txc:EndDeadRun', NS)
    return (get_deadrun_ref(start_element), get_deadrun_ref(end_element))


def get_deadrun_ref(deadrun_element):
    """Given a StartDeadRun or EndDeadRun element with a ShortWorking,
    return the ID of a JourneyPetternTimingLink.
    """
    if deadrun_element is not None:
        element = deadrun_element.find('txc:ShortWorking/txc:JourneyPatternTimingLinkRef', NS)
        if element is not None:
            return element.text
        # ignore PositioningLinks


class VehicleJourneyTimingLink:
    def __init__(self, element):
        self.id = element.attrib.get('id')
        self.journeypatterntiminglinkref = element.find('txc:JourneyPatternTimingLinkRef', NS).text
        self.run_time = element.find('txc:RunTime', NS)
        if self.run_time is not None:
            self.run_time = parse_duration(self.run_time.text)

        self.from_wait_time = element.find('txc:From/txc:WaitTime', NS)
        if self.from_wait_time is not None:
            self.from_wait_time = parse_duration(self.from_wait_time.text)

        self.to_wait_time = element.find('txc:To/txc:WaitTime', NS)
        if self.to_wait_time is not None:
            self.to_wait_time = parse_duration(self.to_wait_time.text)


class VehicleJourney:
    """A journey represents a scheduled journey that happens at most once per
    day. A sort of "instance" of a JourneyPattern, made distinct by having its
    own start time (and possibly operating profile and dead run).
    """
    operating_profile = None
    journey_pattern = None
    journey_ref = None

    def __str__(self):
        return str(self.departure_time)

    def __init__(self, element, services, serviced_organisations):
        self.code = element.find('txc:VehicleJourneyCode', NS).text
        self.private_code = element.find('txc:PrivateCode', NS)
        if self.private_code is not None:
            self.private_code = self.private_code.text

        self.service_ref = element.find('txc:ServiceRef', NS).text
        self.line_ref = element.find('txc:LineRef', NS).text

        journeypatternref_element = element.find('txc:JourneyPatternRef', NS)
        if journeypatternref_element is not None:
            self.journey_pattern = services[self.service_ref].journey_patterns.get(journeypatternref_element.text)
        else:
            # Journey has no direct reference to a JourneyPattern.
            # Instead, it has a reference to another journey...
            self.journey_ref = element.find('txc:VehicleJourneyRef', NS).text

        operatingprofile_element = element.find('txc:OperatingProfile', NS)
        if operatingprofile_element is not None:
            self.operating_profile = OperatingProfile(operatingprofile_element, serviced_organisations)

        departure_time = datetime.datetime.strptime(
            element.find('txc:DepartureTime', NS).text, '%H:%M:%S'
        )
        self.departure_time = datetime.timedelta(hours=departure_time.hour,
                                                 minutes=departure_time.minute,
                                                 seconds=departure_time.second)

        self.start_deadrun, self.end_deadrun = get_deadruns(element)

        self.operator = element.find('txc:OperatorRef', NS)
        if self.operator is not None:
            self.operator = self.operator.text

        sequencenumber = element.get('SequenceNumber')
        self.sequencenumber = sequencenumber and int(sequencenumber)

        timing_links = element.findall('txc:VehicleJourneyTimingLink', NS)
        self.timing_links = [VehicleJourneyTimingLink(timing_link) for timing_link in timing_links]

        note_elements = element.findall('txc:Note', NS)
        if note_elements is not None:
            self.notes = {
                note_element.find('txc:NoteCode', NS).text: note_element.find('txc:NoteText', NS).text
                for note_element in note_elements
            }

    def get_timinglinks(self):
        pattern_links = self.journey_pattern.get_timinglinks()
        if self.timing_links:
            timing_links = iter(self.timing_links)
            journey_link = next(timing_links)
            for link in pattern_links:
                if link.id == journey_link.journeypatterntiminglinkref:
                    yield link, journey_link
                    try:
                        journey_link = next(timing_links)
                    except StopIteration:
                        pass
                else:
                    yield link, None
        else:
            for link in pattern_links:
                yield link, None

    def get_times(self):
        stopusage = None
        time = self.departure_time
        deadrun = self.start_deadrun is not None
        deadrun_next = False
        wait_time = None

        for timinglink, journey_timinglink in self.get_timinglinks():
            stopusage = timinglink.origin

            if deadrun and self.start_deadrun == timinglink.id:
                deadrun = False  # end of dead run

            if journey_timinglink and journey_timinglink.from_wait_time is not None:
                wait_time = journey_timinglink.from_wait_time
            else:
                wait_time = stopusage.wait_time or wait_time

            if wait_time:
                next_time = time + wait_time
                if not deadrun:
                    yield Cell(stopusage, time, next_time)
                time = next_time
            elif not deadrun:
                yield Cell(stopusage, time, time)

            if journey_timinglink and journey_timinglink.run_time is not None:
                run_time = journey_timinglink.run_time
            else:
                run_time = timinglink.runtime
            if run_time:
                time += run_time

            if deadrun_next:
                deadrun = True
                deadrun_next = False
            elif self.end_deadrun == timinglink.id:
                deadrun_next = True  # start of dead run

            stopusage = timinglink.destination

            if journey_timinglink and journey_timinglink.to_wait_time is not None:
                wait_time = journey_timinglink.to_wait_time
            else:
                wait_time = stopusage.wait_time

        if not deadrun:
            yield Cell(timinglink.destination, time, time)


class ServicedOrganisation:
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


class ServicedOrganisationDayType:
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


class DayOfWeek:
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


class OperatingProfile:
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


class DateRange:
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

    def dates(self):
        return PDateRange(self.start, self.end, '[]')


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


class Service:
    description = None
    description_parts = None
    via = None

    def set_description(self, description):
        if description.isupper():
            description = titlecase(description)
        elif ' via ' in description and description[:description.find(' via ')].isupper():
            parts = description.split(' via ')
            parts[0] = titlecase(parts[0])
            description = ' via '.join(parts)
        self.description = correct_description(description)

        self.via = None
        self.description_parts = list(map(sanitize_description_part, self.description.split(' - ')))
        if ' via ' in self.description_parts[-1]:
            self.description_parts[-1], self.via = self.description_parts[-1].split(' via ', 1)

    def __init__(self, element, serviced_organisations, journey_pattern_sections):
        self.element = element

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

        self.origin = element.find('txc:StandardService/txc:Origin', NS).text
        self.destination = element.find('txc:StandardService/txc:Destination', NS).text
        self.vias = element.find('txc:StandardService/txc:Vias', NS)
        if self.vias:
            self.vias = [via.text for via in self.vias]

        self.journey_patterns = {
            journey_pattern.id: journey_pattern for journey_pattern in (
               JourneyPattern(journey_pattern, journey_pattern_sections)
               for journey_pattern in element.findall('txc:StandardService/txc:JourneyPattern', NS)
            ) if journey_pattern.sections
        }


class TransXChange:
    def get_journeys(self, service_code, line_id):
        return [journey for journey in self.journeys
                if journey.service_ref == service_code and journey.line_ref == line_id]

    def __get_journeys(self, journeys_element, serviced_organisations):
        journeys = {
            journey.code: journey for journey in (
                VehicleJourney(element, self.services, serviced_organisations)
                for element in journeys_element
            )
        }

        # Some Journeys do not have a direct reference to a JourneyPattern,
        # but rather a reference to another Journey which has a reference to a JourneyPattern
        for journey in iter(journeys.values()):
            if journey.journey_ref and not journey.journey_pattern:
                journey.journey_pattern = journeys[journey.journey_ref].journey_pattern

        return [journey for journey in journeys.values() if journey.journey_pattern]

    def __init__(self, open_file):
        try:
            detector = UniversalDetector()

            for line in open_file:
                detector.feed(line)
                if detector.done:
                    break
            detector.close()
            encoding = detector.result['encoding']
            if encoding == 'UTF-8-SIG':
                encoding = 'utf-8'
            parser = ET.XMLParser(encoding=encoding)
        except TypeError:
            parser = None

        open_file.seek(0)
        iterator = ET.iterparse(open_file, parser=parser)

        self.services = {}

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
                except (AttributeError, KeyError) as e:
                    logger.error(e, exc_info=True)
                    return
                element.clear()
            elif tag == 'Service':
                service = Service(element, serviced_organisations, journey_pattern_sections)
                self.services[service.service_code] = service

        self.element = element

        self.transxchange_date = max(
            element.attrib['CreationDateTime'], element.attrib['ModificationDateTime']
        )[:10]


class Cell:
    last = False

    def __init__(self, stopusage, arrival_time, departure_time):
        self.stopusage = stopusage
        self.arrival_time = arrival_time
        self.departure_time = departure_time
        self.wait_time = arrival_time and departure_time and arrival_time != departure_time


def stop_is_at(stop, text):
    """Whether a given slugified string, roughly matches either
    this stop's locality's name, or this stop's name
    (e.g. 'kings-lynn' matches 'kings-lynn-bus-station' and vice versa).
    """
    if stop.locality:
        name = slugify(stop.locality)
        if name in text or text in name:
            if name == text:
                return 2
            return 1
    name = slugify(stop.common_name)
    if text in name or name in text:
        if name == text:
            return 2
        return 1
    return False


class Grouping:
    def __init__(self, parent, origin, destination):
        self.description_parts = parent.description_parts
        self.via = parent.via
        self.origin = origin
        self.destination = destination

    def starts_at(self, text):
        return stop_is_at(self.origin, text)

    def ends_at(self, text):
        return stop_is_at(self.destination, text)

    def __str__(self):
        parts = self.description_parts

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
                if self.via:
                    description += ' via ' + self.via
                return description

        return ''

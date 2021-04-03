import re
import xml.etree.cElementTree as ET
import calendar
import datetime
import logging
from psycopg2.extras import DateRange as PDateRange
from django.contrib.gis.geos import Point, LineString
from django.utils.text import slugify
from django.utils.dateparse import parse_duration
from chardet.universaldetector import UniversalDetector
from titlecase import titlecase


logger = logging.getLogger(__name__)


WEEKDAYS = {day: i for i, day in enumerate(calendar.day_name)}


DESCRIPTION_REGEX = re.compile(r'.+,([^ ].+)$')


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
    def __init__(self, element):
        if element:
            self.atco_code = element.findtext('StopPointRef')
            if not self.atco_code:
                self.atco_code = element.findtext('AtcoCode', '')

            self.common_name = element.findtext('CommonName')

            self.locality = element.findtext('LocalityName')

    def __str__(self):
        if not self.locality or self.locality in self.common_name:
            return self.common_name or self.atco_code
        return f'{self.locality} {self.common_name}'


class Route:
    def __init__(self, element):
        self.id = element.get('id')
        self.route_section_refs = [section.text for section in element.findall('RouteSectionRef')]


class RouteSection:
    def __init__(self, element):
        self.id = element.get('id')
        self.links = [RouteLink(link) for link in element.findall('RouteLink')]


class RouteLink:
    def __init__(self, element):
        self.id = element.get('id')
        locations = element.findall('Track/Mapping/Location/Translation')
        if not locations:
            locations = element.findall('Track/Mapping/Location')
        locations = (Point(
            float(location.find('Longitude').text),
            float(location.find('Latitude').text)
        ) for location in locations)
        self.track = LineString(*locations)


class JourneyPattern:
    """A collection of JourneyPatternSections, in order."""
    def __init__(self, element, sections, serviced_organisations):
        self.id = element.attrib.get('id')
        self.sections = [
            sections[section_element.text]
            for section_element in element.findall('JourneyPatternSectionRefs')
            if section_element.text in sections
        ]

        self.route_ref = element.findtext('RouteRef')
        self.direction = element.findtext('Direction')
        if self.direction and self.direction != 'inbound' and self.direction != 'outbound':
            # clockwise/anticlockwise? Not supported, not sure if that's a problem
            self.direction = self.direction.lower()

        self.operating_profile = element.find('OperatingProfile')
        if self.operating_profile is not None:
            self.operating_profile = OperatingProfile(self.operating_profile, serviced_organisations)

    def is_inbound(self):
        return self.direction in ('inbound', 'anticlockwise')

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
    sequencenumber = None

    """Either a 'From' or 'To' element in TransXChange."""
    def __init__(self, element, stops):
        self.activity = element.findtext('Activity')

        sequencenumber = element.get('SequenceNumber')
        if sequencenumber is not None:
            self.sequencenumber = int(sequencenumber)

        self.stop = stops.get(element.find('StopPointRef').text)
        if self.stop is None:
            self.stop = Stop(element)

        self.timingstatus = element.findtext('TimingStatus')

        self.wait_time = element.find('WaitTime')
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
        self.origin = JourneyPatternStopUsage(element.find('From'), stops)
        self.destination = JourneyPatternStopUsage(element.find('To'), stops)
        self.origin.parent = self.destination.parent = self
        self.runtime = parse_duration(element.find('RunTime').text)
        self.id = element.get('id')
        self.route_link_ref = element.findtext('RouteLinkRef')


def get_deadruns(journey_element):
    """Given a VehicleJourney element, return a tuple."""
    start_element = journey_element.find('StartDeadRun')
    end_element = journey_element.find('EndDeadRun')
    return (get_deadrun_ref(start_element), get_deadrun_ref(end_element))


def get_deadrun_ref(deadrun_element):
    """Given a StartDeadRun or EndDeadRun element with a ShortWorking,
    return the ID of a JourneyPetternTimingLink.
    """
    if deadrun_element is not None:
        return deadrun_element.findtext('ShortWorking/JourneyPatternTimingLinkRef')
        # ignore PositioningLinks


class VehicleJourneyTimingLink:
    def __init__(self, element):
        self.id = element.attrib.get('id')
        self.journeypatterntiminglinkref = element.find('JourneyPatternTimingLinkRef').text
        self.run_time = element.find('RunTime')
        if self.run_time is not None:
            self.run_time = parse_duration(self.run_time.text)

        self.from_wait_time = element.find('From/WaitTime')
        if self.from_wait_time is not None:
            self.from_wait_time = parse_duration(self.from_wait_time.text)

        self.to_wait_time = element.find('To/WaitTime')
        if self.to_wait_time is not None:
            self.to_wait_time = parse_duration(self.to_wait_time.text)


class VehicleType:
    def __init__(self, element):
        self.code = element.findtext('VehicleTypeCode')
        self.description = element.findtext('Description')


class VehicleJourney:
    """A scheduled journey that happens at most once per day"""
    operating_profile = None
    journey_pattern = None
    journey_ref = None
    block = None
    garage_ref = None

    def __str__(self):
        return str(self.departure_time)

    def __init__(self, element, services, serviced_organisations):
        self.code = element.find('VehicleJourneyCode').text
        self.private_code = element.findtext('PrivateCode')

        self.ticket_machine_journey_code = element.findtext('Operational/TicketMachine/JourneyCode')
        self.ticket_machine_service_code = element.findtext('Operational/TicketMachine/TicketMachineServiceCode')
        self.block = element.findtext('Operational/Block/BlockNumber')
        self.garage_ref = element.findtext('GarageRef')

        self.service_ref = element.find('ServiceRef').text
        self.line_ref = element.find('LineRef').text

        journeypatternref_element = element.find('JourneyPatternRef')
        if journeypatternref_element is not None:
            self.journey_pattern = services[self.service_ref].journey_patterns.get(journeypatternref_element.text)
        else:
            # Journey has no direct reference to a JourneyPattern.
            # Instead, it has a reference to another journey...
            self.journey_ref = element.find('VehicleJourneyRef').text

        operatingprofile_element = element.find('OperatingProfile')
        if operatingprofile_element is not None:
            self.operating_profile = OperatingProfile(operatingprofile_element, serviced_organisations)

        hours, minutes, seconds = element.find('DepartureTime').text.split(':')
        self.departure_time = datetime.timedelta(hours=int(hours), minutes=int(minutes), seconds=int(seconds))
        departure_day_shift = element.findtext('DepartureDayShift')
        if departure_day_shift:
            self.departure_time += datetime.timedelta(days=int(departure_day_shift))

        self.start_deadrun, self.end_deadrun = get_deadruns(element)

        self.operator = element.findtext('OperatorRef')

        sequencenumber = element.get('SequenceNumber')
        self.sequencenumber = sequencenumber and int(sequencenumber)

        timing_links = element.findall('VehicleJourneyTimingLink')
        self.timing_links = [VehicleJourneyTimingLink(timing_link) for timing_link in timing_links]

        note_elements = element.findall('Note')
        if note_elements is not None:
            self.notes = {
                note_element.find('NoteCode').text: note_element.find('NoteText').text
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
    """Like a school, college, or workplace"""
    def __init__(self, element):
        self.code = element.find('OrganisationCode').text
        self.name = element.findtext('Name')

        working_days_element = element.find('WorkingDays')
        if working_days_element is not None:
            self.working_days = [DateRange(e) for e in working_days_element.findall('DateRange')]
        else:
            self.working_days = []

        holidays_element = element.find('Holidays')
        if holidays_element is not None:
            self.holidays = [DateRange(e) for e in holidays_element.findall('DateRange')]
        else:
            self.holidays = []


class ServicedOrganisationDayType:
    non_operation_holidays = None
    non_operation_working_days = None
    operation_holidays = None
    operation_working_days = None

    def __init__(self, element, serviced_organisations):
        if not serviced_organisations:
            return

        organisation_ref = element.findtext('DaysOfOperation/Holidays/ServicedOrganisationRef')
        if organisation_ref:
            self.operation_holidays = serviced_organisations[organisation_ref]
            if not self.operation_holidays.holidays and self.operation_holidays.working_days:
                self.non_operation_working_days = self.operation_holidays
                self.operation_holidays = None

        organisation_ref = element.findtext('DaysOfNonOperation/Holidays/ServicedOrganisationRef')
        if organisation_ref:
            self.non_operation_holidays = serviced_organisations[organisation_ref]
            if not self.non_operation_holidays.holidays and self.non_operation_holidays.working_days:
                self.operation_working_days = self.non_operation_holidays
                self.non_operation_holidays = None

        organisation_ref = element.findtext('DaysOfOperation/WorkingDays/ServicedOrganisationRef')
        if organisation_ref:
            self.operation_working_days = serviced_organisations[organisation_ref]
            if not self.operation_working_days.working_days and self.operation_working_days.holidays:
                self.non_operation_holidays = self.operation_working_days
                self.operation_working_days = None

        organisation_ref = element.findtext('DaysOfNonOperation/WorkingDays/ServicedOrganisationRef')
        if organisation_ref:
            self.non_operation_working_days = serviced_organisations[organisation_ref]
            if not self.non_operation_working_days.working_days and self.non_operation_working_days.holidays:
                self.operation_holidays = self.non_operation_working_days
                self.non_operation_working_days = None


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
    serviced_organisation_day_type = None
    nonoperation_days = ()
    operation_days = ()

    def __init__(self, element, serviced_organisations):
        element = element

        week_days_element = element.find('RegularDayType/DaysOfWeek')
        self.regular_days = []
        if week_days_element is not None:
            for day in [e.tag for e in week_days_element]:
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

        special_days_element = element.find('SpecialDaysOperation')

        if special_days_element is not None:
            nonoperation_days_element = special_days_element.find('DaysOfNonOperation')

            if nonoperation_days_element is not None:
                self.nonoperation_days = list(map(DateRange, nonoperation_days_element.findall('DateRange')))

            operation_days_element = special_days_element.find('DaysOfOperation')

            if operation_days_element is not None:
                self.operation_days = list(map(DateRange, operation_days_element.findall('DateRange')))

        # Serviced Organisation:

        serviced_organisation_day_type_element = element.find('ServicedOrganisationDayType')

        if serviced_organisation_day_type_element is not None:
            self.serviced_organisation_day_type = ServicedOrganisationDayType(serviced_organisation_day_type_element,
                                                                              serviced_organisations)

        # Bank Holidays

        self.operation_bank_holidays = element.find('BankHolidayOperation/DaysOfOperation')
        self.nonoperation_bank_holidays = element.find('BankHolidayOperation/DaysOfNonOperation')


class DateRange:
    def __init__(self, element):
        self.start = element.findtext("StartDate")
        self.end = element.findtext("EndDate")
        try:
            self.start = datetime.date.fromisoformat(self.start)
        except ValueError:  # Sanders Coaches. There's no way this is valid
            self.start = datetime.datetime.strptime(self.start, '%m/%d/%Y').date()
            if self.end:
                self.end = datetime.datetime.strptime(self.end, '%m/%d/%Y').date()
        else:
            if self.end:
                self.end = datetime.date.fromisoformat(self.end)
        self.note = element.findtext("Note", "")

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
    operating_profile = None

    def set_description(self, description):
        if description.isupper():
            description = titlecase(description)
        elif ' via ' in description and description[:description.find(' via ')].isupper():
            parts = description.split(' via ')
            description = ' via '.join(titlecase(part) for part in parts)
        self.description = correct_description(description)

        self.via = None
        if ' - ' in self.description:
            parts = self.description.split(' - ')
        elif ' to ' in self.description:
            parts = self.description.split(' to ')
        else:
            parts = [self.description]
        self.description_parts = [sanitize_description_part(part) for part in parts]
        if ' via ' in self.description_parts[-1]:
            self.description_parts[-1], self.via = self.description_parts[-1].split(' via ', 1)

    def __init__(self, element, serviced_organisations, journey_pattern_sections):
        self.mode = element.findtext('Mode', '')

        self.operator = element.findtext('RegisteredOperatorRef')

        operatingprofile_element = element.find('OperatingProfile')
        if operatingprofile_element is not None:
            self.operating_profile = OperatingProfile(operatingprofile_element, serviced_organisations)

        self.operating_period = OperatingPeriod(element.find('OperatingPeriod'))

        self.public_use = element.findtext('PublicUse')

        self.service_code = element.find('ServiceCode').text

        self.marketing_name = element.findtext('MarketingName')

        description = element.findtext('Description')
        if description:
            self.set_description(description.strip())

        self.origin = element.findtext('StandardService/Origin')
        if self.origin:
            self.origin = self.origin.replace('`', "'").strip()

        self.destination = element.findtext('StandardService/Destination')
        if self.destination:
            self.destination = self.destination.replace('`', "'").strip()

        self.vias = element.find('StandardService/Vias')
        if self.vias:
            self.vias = [via.text for via in self.vias]

        self.journey_patterns = {
            journey_pattern.id: journey_pattern for journey_pattern in (
               JourneyPattern(journey_pattern, journey_pattern_sections, serviced_organisations)
               for journey_pattern in element.findall('StandardService/JourneyPattern')
            ) if journey_pattern.sections
        }

        self.lines = [
            Line(line_element) for line_element in element.find('Lines')
        ]


class Line:
    def __init__(self, element):
        self.id = element.attrib['id']
        line_name = element.findtext('LineName') or ''
        if '|' in line_name:
            line_name, line_brand = line_name.split('|', 1)
            self.line_brand = line_brand.strip()
        else:
            self.line_brand = ''
        self.line_name = line_name.strip()

        self.outbound_description = element.findtext('OutboundDescription/Description')
        self.inbound_description = element.findtext('InboundDescription/Description')


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
            if journey.journey_ref:
                referenced_journey = journeys[journey.journey_ref]
                if journey.journey_pattern is None:
                    journey.journey_pattern = referenced_journey.journey_pattern
                if journey.operating_profile is None:
                    journey.operating_profile = referenced_journey.operating_profile

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
        self.stops = {}
        self.routes = {}
        self.route_sections = {}
        self.journeys = []
        self.garages = {}

        serviced_organisations = None

        journey_pattern_sections = {}

        for _, element in iterator:
            if element.tag[:33] == '{http://www.transxchange.org.uk/}':
                element.tag = element.tag[33:]
            tag = element.tag

            if tag == 'StopPoints':
                for stop_element in element:
                    stop = Stop(stop_element)
                    self.stops[stop.atco_code] = stop
                element.clear()
            elif tag == 'RouteSections':
                for section_element in element:
                    section = RouteSection(section_element)
                    self.route_sections[section.id] = section
                element.clear()
            elif tag == 'Routes':
                for route_element in element:
                    route = Route(route_element)
                    self.routes[route.id] = route
                element.clear()
            elif tag == 'RouteSections':
                element.clear()
            elif tag == 'Operators':
                self.operators = element
            elif tag == 'JourneyPatternSections':
                for section in element:
                    section = JourneyPatternSection(section, self.stops)
                    if section.timinglinks:
                        journey_pattern_sections[section.id] = section
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
            elif tag == 'Garages':
                for garage_element in element:
                    self.garages[garage_element.findtext('GarageCode')] = garage_element
                element.clear()

        self.attributes = element.attrib


class Cell:
    last = False

    def __init__(self, stopusage, arrival_time, departure_time):
        self.stopusage = stopusage
        self.arrival_time = arrival_time
        self.departure_time = departure_time
        if arrival_time is not None and departure_time is not None and arrival_time != departure_time:
            self.wait_time = True
        else:
            self.wait_time = None


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

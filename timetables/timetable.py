import os
import re
import xml.etree.cElementTree as ET
from datetime import date, datetime, timedelta

DIR = os.path.dirname(__file__)
NS = {
    'txc': 'http://www.transxchange.org.uk/'
}
DURATION_REGEX = re.compile(
    r'PT((?P<hours>\d+?)H)?((?P<minutes>\d+?)M)?((?P<seconds>\d+?)S)?'
)
NOW = date.today()

def parse_duration(string):
    "Given a string returns a timetelta"

    matches = DURATION_REGEX.match(string).groupdict().iteritems()
    params = {
        key: int(value) for key, value in matches if value is not None
    }
    return timedelta(**params)


class Stop(object):
    def __init__(self, element, stops):
        self.atco_code = element.find('txc:StopPointRef', NS).text
        if stops is not None:
            self.stop = stops.get(self.atco_code)
        self.common_name = element.find('txc:CommonName', NS).text
        locality_element = element.find('txc:LocalityName', NS)
        if locality_element is not None:
            self.locality = locality_element.text
        else:
            self.locality = None

    def __unicode__(self):
        if self.locality is None or self.locality in self.common_name:
            return self.common_name
        else:
            return '%s %s' % (self.locality, self.common_name)


class Row(object):
    def __init__(self, part):
        self.part = part
        part.row = self
        self.times = []
        self.sequencenumbers = {}

    def __lt__(self, other):
        for key in self.sequencenumbers:
            if key in other.sequencenumbers:
                return self.sequencenumbers[key] < other.sequencenumbers[key]
        return max(self.sequencenumbers.values()) < max(other.sequencenumbers.values())


class Grouping(object):
    def __init__(self, direction):
        self.direction = direction
        self.column_heads = []
        self.column_feet = []
        self.journeys = []
        self.rows = {}

    def has_minor_stops(self):
        for row in self.rows:
            if row.part.timingstatus == 'OTH':
                return True
        return False


class JourneyPattern(object):
    def __init__(self, element, sections, outbound_grouping, inbound_grouping):
        self.id = element.attrib.get('id')
        self.journeys = []
        self.sections = [
            sections[section_element.text]
            for section_element in element.findall('txc:JourneyPatternSectionRefs', NS)
        ]

        origin = self.sections[0].timinglinks[0].origin

        self.rows = []
        self.rows.append(Row(origin))
        for section in self.sections:
            for timinglink in section.timinglinks:
                self.rows.append(Row(timinglink.destination))

        direction_element = element.find('txc:Direction', NS)
        if direction_element is not None and direction_element.text == 'outbound':
            self.grouping = outbound_grouping
        else:
            self.grouping = inbound_grouping

        if origin.sequencenumber is not None:
            for row in self.rows:
                if row.part.sequencenumber not in self.grouping.rows:
                    self.grouping.rows[row.part.sequencenumber] = row
        else:
            visited_stops = []
            i = 0
            for row in self.rows:
                if row.part.stop.atco_code not in self.grouping.rows:
                    self.grouping.rows[row.part.stop.atco_code] = row
                    row.sequencenumbers[self.id] = i
                elif row.part.stop.atco_code in visited_stops:
                    self.grouping.rows[i] = row
                    row.part.row = row
                    row.sequencenumbers[self.id] = i
                else:
                    row.part.row = self.grouping.rows[row.part.stop.atco_code]
                    row.part.row.sequencenumbers[self.id] = i
                i += 1
                visited_stops.append(row.part.stop.atco_code)


class JourneyPatternSection(object):
    def __init__(self, element, stops):
        self.timinglinks = [
            JourneyPatternTimingLink(timinglink_element, stops)
            for timinglink_element in element
        ]


class JourneyPatternStopUsage(object):
    """Represents either a 'From' or 'To' element in TransXChange"""
    def __init__(self, element, stops):
        # self.activity = element.find('txc:Activity', NS).text
        self.sequencenumber = element.get('SequenceNumber')
        if self.sequencenumber is not None:
            self.sequencenumber = int(self.sequencenumber)
        self.stop = stops.get(element.find('txc:StopPointRef', NS).text)
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


class VehicleJourney(object):
    def __init__(self, element, journeypatterns, servicedorganisations):
        self.departure_time = datetime.strptime(
            element.find('txc:DepartureTime', NS).text, '%H:%M:%S'
        ).time()

        journeypatternref_element = element.find('txc:JourneyPatternRef', NS)
        if journeypatternref_element is not None:
            self.journeypattern = journeypatterns[journeypatternref_element.text]
        else:
            # Journey has no direct reference to a JourneyPattern
            # instead it as a reference to a similar journey with does
            self.journeyref = element.find('txc:VehicleJourneyRef', NS).text

        start_deadrun_element = element.find('txc:StartDeadRun', NS)
        if start_deadrun_element is not None:
            self.start_deadrun = start_deadrun_element.find('txc:ShortWorking', NS).find('txc:JourneyPatternTimingLinkRef', NS).text
        end_deadrun_element = element.find('txc:EndDeadRun', NS)
        if end_deadrun_element is not None:
            self.end_deadrun = end_deadrun_element.find('txc:ShortWorking', NS).find('txc:JourneyPatternTimingLinkRef', NS).text

        note_elements = element.findall('txc:Note', NS)
        if note_elements is not None:
            self.notes = [note_element.find('txc:NoteText', NS).text for note_element in note_elements]

        operatingprofile_element = element.find('txc:OperatingProfile', NS)
        if operatingprofile_element is not None:
            self.operating_profile = OperatingProfile(operatingprofile_element, servicedorganisations)

    def add_times(self):
        row_length = len(self.journeypattern.grouping.rows.values()[0].times)

        stopusage = self.journeypattern.sections[0].timinglinks[0].origin
        time = self.departure_time
        if stopusage.sequencenumber is not None:
            self.journeypattern.grouping.rows.get(stopusage.sequencenumber).times.append(time)
        else:
            stopusage.row.times.append(time)

        deadrun = hasattr(self, 'start_deadrun')
        for section in self.journeypattern.sections:
            for timinglink in section.timinglinks:
                stopusage = timinglink.destination
                time = (datetime.combine(date.today(), time) + timinglink.runtime).time()

                if deadrun and hasattr(self, 'start_deadrun') and self.start_deadrun == timinglink.id:
                    deadrun = False
                if not deadrun:
                    if stopusage.sequencenumber is not None:
                        row = self.journeypattern.grouping.rows.get(stopusage.sequencenumber)
                        row.times.append(time)
                    else:
                        stopusage.row.times.append(time)

                if hasattr(self, 'end_deadrun') and self.end_deadrun == timinglink.id:
                    deadrun = True
                if hasattr(stopusage, 'waittime'):
                    time = (datetime.combine(date.today(), time) + stopusage.waittime).time()

        for row in self.journeypattern.grouping.rows.values():
            if len(row.times) == row_length:
                row.times.append('')

    def get_departure_time(self):
        return self.departure_time

    def get_order(self):
        if hasattr(self, 'operating_profile'):
            return self.operating_profile.get_order()
        return 0

    def should_show(self):
        if not hasattr(self, 'operating_profile'):
            return True
        if str(self.operating_profile) == 'HolidaysOnlys':
            return False
        if hasattr(self.operating_profile, 'nonoperation_days') and self.operating_profile is not None:
            for daterange in self.operating_profile.nonoperation_days:
                if daterange.finishes_in_past() or daterange.starts_in_future():
                    return True
            return False
        return True


# class ServicedOrganisation(object):


class OperatingProfile(object):
    def __init__(self, element, servicedorganisations):
        element = element

        regular_days_element = element.find('txc:RegularDayType', NS)
        week_days_element = regular_days_element.find('txc:DaysOfWeek', NS)

        if week_days_element is None:
            self.regular_days = [e.tag[33:] for e in regular_days_element]
        else:
            self.regular_days = [e.tag[33:] for e in week_days_element]


        special_days_element = element.find('txc:SpecialDaysOperation', NS)

        if special_days_element is not None:
            nonoperation_days_element = special_days_element.find('txc:DaysOfNonOperation', NS)

            if nonoperation_days_element is not None:
                self.nonoperation_days = map(DateRange, nonoperation_days_element.findall('txc:DateRange', NS))

            operation_days_element = special_days_element.find('txc:DaysOfOperation', NS)

            if operation_days_element is not None:
                self.operation_days = map(DateRange, operation_days_element.findall('txc:DateRange', NS))


        servicedorg_days_element = element.find('txc:ServicedOrganisationDayType', NS)
        if servicedorg_days_element is not None:

            # days of non operation
            servicedorg_noop_element = servicedorg_days_element.find('txc:DaysOfNonOperation', NS)
            if servicedorg_noop_element is not None:
                noop_hols_element = servicedorg_noop_element.find('txc:Holidays', NS)
                noop_workingdays_element = servicedorg_noop_element.find('txc:WorkingDays', NS)

                if noop_hols_element is not None:
                    self.servicedorganisation_nonoperation_holidays = noop_hols_element.find('txc:ServicedOrganisationRef', NS).text

                if noop_workingdays_element is not None:
                    self.servicedorganisation_nonoperation_workingdays = noop_workingdays_element.find('txc:ServicedOrganisationRef', NS).text

            # days of operation
            servicedorg_op_element = servicedorg_days_element.find('txc:DaysOfOperation', NS)
            if servicedorg_op_element is not None:
                op_hols_element = servicedorg_op_element.find('txc:Holidays', NS)
                op_workingdays_element = servicedorg_op_element.find('txc:WorkingDays', NS)

                if op_hols_element is not None:
                    self.servicedorganisation_operation_holidays = op_hols_element.find('txc:ServicedOrganisationRef', NS).text

                if op_workingdays_element is not None:
                    self.servicedorganisation_operation_workingdays = op_workingdays_element.find('txc:ServicedOrganisationRef', NS).text


    def __str__(self):
        if len(self.regular_days) == 1:
            if 'To' in self.regular_days[0]:
                string = self.regular_days[0].replace('To', ' to ')
            else:
                string = self.regular_days[0] + 's'

        else:
            string = 's, '.join(self.regular_days[:-1]) + 's and ' + self.regular_days[-1] + 's'

            if string == 'Mondays, Tuesdays, Wednesdays, Thursdays and Fridays':
                string = 'Monday to Friday'
            elif string == 'Mondays, Tuesdays, Wednesdays, Thursdays, Fridays and Saturdays':
                string = 'Monday to Saturday'
            elif string == 'Mondays, Tuesdays, Wednesdays, Thursdays, Fridays, Saturdays and Sundays':
                string = 'Monday to Sunday'

        # if hasattr(self, 'nonoperation_days'):
        #     string = string + '\nNot ' + ', '.join(map(str, self.nonoperation_days))

        # if hasattr(self, 'operation_days'):
        #     string = string + '\n' + ', '.join(map(str, self.operation_days))

        if hasattr(self, 'servicedorganisation_nonoperation_holidays'):
            string = string + '\nSchool days'
        if hasattr(self, 'servicedorganisation_operation_holidays'):
            string = string + '\nSchool holidays'
        if hasattr(self, 'servicedorganisation_nonoperation_workingdays'):
            string = string + '\nSchool holidays'
        if hasattr(self, 'servicedorganisation_operation_workingdays'):
            string = string + '\nSchool days'

        return string

    def get_order(self):
        if self.regular_days[0][:3] == 'Mon':
            return 0
        if self.regular_days[0][:3] == 'Sat':
            return 1
        if self.regular_days[0][:3] == 'Sun':
            return 2
        if self.regular_days[0][:3] == 'Hol':
            return 3
        return 0

    def __ne__(self, other):
        return str(self) != str(other)


class DateRange(object):
    def __init__(self, element):
        self.start = datetime.strptime(element.find('txc:StartDate', NS).text, '%Y-%m-%d').date()
        end = element.find('txc:EndDate', NS)
        self.end = datetime.strptime(end.text, '%Y-%m-%d').date() if end is not None else None

    def __str__(self):
        if self.start == self.end:
            return self.start.strftime('%-d %B %Y')
        else:
            return '%s to %s' % (str(self.start), str(self.end))

    def starts_in_future(self):
        return self.start > NOW

    def finishes_in_past(self):
        return self.end < NOW


class OperatingPeriod(DateRange):
    def __str__(self):
        if self.start == self.end:
            return self.start.strftime('on %-d %B %Y')
        elif self.starts_in_future():
            if self.end is None:
                return self.start.strftime('from %-d %B %Y')
            elif self.end is not None and self.start.year == self.end.year:
                if self.start.month == self.end.month:
                    start_format = '%-d'
                else:
                    start_format = '%-d %B'
            else:
                start_format = '%-d %B %Y'
            return 'from %s to %s' % (self.start.strftime(start_format), self.end.strftime('%-d %B %Y'))
        return ''


class ColumnHead(object):
    def __init__(self, operatingprofile, span):
        self.operatingprofile = operatingprofile
        self.span = span


class ColumnFoot(object):
    def __init__(self, notes, span):
        self.notes = notes
        self.span = span


class Timetable(object):
    def __init__(self, xml, stops=None):
        outbound_grouping = Grouping('outbound')
        inbound_grouping = Grouping('inbound')

        stops = {
            element.find('txc:StopPointRef', NS).text: Stop(element, stops)
            for element in xml.find('txc:StopPoints', NS)
        }
        journeypatternsections = {
            element.get('id'): JourneyPatternSection(element, stops)
            for element in xml.find('txc:JourneyPatternSections', NS)
        }
        journeypatterns = {
            element.get('id'): JourneyPattern(element, journeypatternsections, outbound_grouping, inbound_grouping)
            for element in xml.findall('.//txc:JourneyPattern', NS)
        }

        servicedorganisations = xml.find('txc:ServicedOrganisations', NS)

        # time calculation begins here:
        journeys = {
            element.find('txc:VehicleJourneyCode', NS).text: VehicleJourney(element, journeypatterns, servicedorganisations)
            for element in xml.find('txc:VehicleJourneys', NS)
        }

        # some journeys did not have a direct reference to a journeypattern,
        # but rather a reference to another journey with a reference to a journeypattern
        for journey in journeys.values():
            if hasattr(journey, 'journeyref'):
                journey.journeypattern = journeys[journey.journeyref].journeypattern

        journeys = journeys.values()
        journeys.sort(key=VehicleJourney.get_departure_time)
        journeys.sort(key=VehicleJourney.get_order)
        for journey in journeys:
            if journey.should_show():
                journey.journeypattern.grouping.journeys.append(journey)
                journey.add_times()

        service_element = xml.find('txc:Services', NS).find('txc:Service', NS)
        operatingprofile_element = service_element.find('txc:OperatingProfile', NS)
        if operatingprofile_element is not None:
            self.operating_profile = OperatingProfile(operatingprofile_element, servicedorganisations)

        self.operating_period = OperatingPeriod(service_element.find('txc:OperatingPeriod', NS))

        self.groupings = (outbound_grouping, inbound_grouping)
        for grouping in self.groupings:
            grouping.rows = grouping.rows.values()
            if len(grouping.rows) and grouping.rows[0].part.sequencenumber is None:
                grouping.rows.sort()

            previous_operatingprofile = None
            previous_notes = None
            head_span = 0
            foot_span = 0
            for journey in grouping.journeys:
                if not hasattr(journey, 'operating_profile'):
                    previous_operatingprofile = None
                else:
                    if previous_operatingprofile != journey.operating_profile:
                        if previous_operatingprofile is not None:
                            grouping.column_heads.append(ColumnHead(previous_operatingprofile, head_span))
                            head_span = 0
                        previous_operatingprofile = journey.operating_profile
                if not hasattr(journey, 'notes'):
                    previous_notes = None
                else:
                    if str(previous_notes) != str(journey.notes):
                        if previous_notes is not None:
                            grouping.column_feet.append(ColumnFoot(previous_notes, foot_span))
                            foot_span = 0
                        previous_notes = journey.notes
                head_span += 1
                foot_span += 1
            grouping.column_heads.append(ColumnHead(previous_operatingprofile, head_span))
            grouping.column_feet.append(ColumnFoot(previous_notes, foot_span))


def get_filenames(service, path):
    if service.region_id == 'NE':
        return (service.pk + '.xml',)
    elif service.region_id in ('S', 'NW'):
        return ('SVR' + service.pk + '.xml',)
    else:
        try:
            namelist = os.listdir(path)
        except OSError:
            return ()
        if service.net:
            return (name for name in namelist if name.startswith(service.pk + '-'))
        elif service.region_id == 'GB':
            parts = service.pk.split('_')
            return (name for name in namelist if name.endswith('_' + parts[1] + '_' + parts[0] + '.xml'))
        elif service.region_id == 'Y':
            return (name for name in namelist if name.startswith(service.pk + '-') or name == 'SVR' + service.pk + '.xml')
        else:
            return (name for name in namelist if name.endswith('_' + service.pk + '.xml'))


def timetable_from_filename(filename, stops):
    try:
        with open(filename) as file:
            xml = ET.parse(file).getroot()
        return Timetable(xml, stops)
    except (IOError):
        return None


def timetable_from_service(service, stops):
    if service.region_id == 'GB':
        # service.service_code = '_'.join(service.service_code.split('_')[::-1])
        path = os.path.join(DIR, '../data/TNDS/NCSD/NCSD_TXC/')
    else:
        path = os.path.join(DIR, '../data/TNDS/%s/' % service.region_id)

    filenames = get_filenames(service, path)

    stops = {stop.atco_code: stop for stop in stops}

    return filter(None, (timetable_from_filename(os.path.join(path, filename), stops) for filename in filenames))

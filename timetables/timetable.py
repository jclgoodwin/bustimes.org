import os
import re
import zipfile
import xml.etree.cElementTree as ET
from datetime import date, datetime, timedelta


DIR = os.path.dirname(__file__)
NS = {
    'txc': 'http://www.transxchange.org.uk/'
}
DURATION_REGEX = re.compile(
    r'PT((?P<hours>\d+?)H)?((?P<minutes>\d+?)M)?((?P<seconds>\d+?)S)?'
)


def parse_duration(string):
    "Given a string returns a timetelta"

    matches = DURATION_REGEX.match(string).groupdict().iteritems()
    params = {
        key: int(value) for key, value in matches if value is not None
    }
    return timedelta(**params)


class Stop(object):
    def __init__(self, element):
        self.atco_code = element.find('txc:StopPointRef', NS).text
        self.common_name = element.find('txc:CommonName', NS).text
        locality_element = element.find('txc:LocalityName', NS)
        if locality_element is not None:
            self.locality = locality_element.text.replace(' (Norfk)', '')#.replace(' City Centre', '').replace(' (Town Centre)', '') 
        else:
            self.locality = None

    def __str__(self):
        if self.locality is None or self.locality in self.common_name:
            return self.common_name
        else:
            return '%s %s' % (self.locality, self.common_name)

    def get_absolute_url(self):
        return '/stops/%s' % self.atco_code


class Row(object):
    def __init__(self, part):
        self.part = part
        self.times = []

    def get_sequencenumber(self):
        if self.part.sequencenumber:
            return self.part.sequencenumber
        elif len(self.part.sequencenumbers):
            return max(self.part.sequencenumbers)
        return 0

class Grouping(object):
    def __init__(self, direction):
        self.direction = direction
        self.journeys = []
        self.rows = {}


class JourneyPattern(object):
    def __init__(self, element, sections, outbound_grouping, inbound_grouping):
        self.journeys = []
        self.sections = [
            sections[section_element.text]
            for section_element in element.findall('txc:JourneyPatternSectionRefs', NS)
        ]
        self.rows = {}
        self.rows[self.sections[0].timinglinks[0].origin.stop.atco_code] = Row(self.sections[0].timinglinks[0].origin)

        for section in self.sections:
            for timinglink in section.timinglinks:
                self.rows[timinglink.destination.stop.atco_code] = Row(timinglink.destination)

        direction = element.find('txc:Direction', NS).text
        if direction == 'outbound':
            self.grouping = outbound_grouping
        else:
            self.grouping = inbound_grouping
        for atco_code, row in self.rows.iteritems():
            self.grouping.rows[atco_code] = row

    def is_outbound(self):
        return self.direction == 'outbound'

    def is_inbound(self):
        return self.direction == 'inbound'

    def __str__(self):
        rows = self.rows.values()
        return '%s to %s' % (rows[0].part.stop, rows[-1].part.stop)


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
        else:
            self.sequencenumbers = []
        self.stop = stops.get(element.find('txc:StopPointRef', NS).text)
        self.timingstatus = element.find('txc:TimingStatus', NS).text

        waittime_element = element.find('txc:WaitTime', NS)
        if waittime_element is not None:
            self.waittime = parse_duration(waittime_element.text)


class JourneyPatternTimingLink(object):
    def __init__(self, element, stops):
        self.origin = JourneyPatternStopUsage(element.find('txc:From', NS), stops)
        self.destination = JourneyPatternStopUsage(element.find('txc:To', NS), stops)
        self.runtime = parse_duration(element.find('txc:RunTime', NS).text)


class VehicleJourney(object):
    def __init__(self, element, journeypatterns):
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

        note_elements = element.findall('txc:Note', NS)
        if note_elements is not None:
            self.notes = [note_element.find('txc:NoteText', NS).text for note_element in note_elements]

        operatingprofile_element = element.find('txc:OperatingProfile', NS)
        if operatingprofile_element is not None:
            self.operating_profile = OperatingProfile(operatingprofile_element)

    def set_journeypattern(self):
        journeypattern.journeys.append(self)
        journeypattern.grouping.journeys.append(self)

    def add_times(self):
        stopusage = self.journeypattern.sections[0].timinglinks[0].origin
        time = self.departure_time
        row = self.journeypattern.grouping.rows.get(stopusage.stop.atco_code)
        row.times.append(time)

        if row.part.sequencenumber is None:
            i = 1
            row.part.sequencenumbers.append(i)

        for section in self.journeypattern.sections:
            for timinglink in section.timinglinks:
                stopusage = timinglink.destination
                time = (datetime.combine(date.today(), time) + timinglink.runtime).time()
                row = self.journeypattern.grouping.rows.get(stopusage.stop.atco_code)
                row.times.append(time)

                if row.part.sequencenumber is None:
                    i += 1
                    row.part.sequencenumbers.append(i)

        # bulk out other rows
        row_length = len(row.times)
        for row in self.journeypattern.grouping.rows.values():
            if len(row.times) < row_length:
                row.times.append('')

    def get_departure_time(self):
        return self.departure_time

    def get_order(self):
        if hasattr(self, 'operating_profile'):
            return self.operating_profile.get_order()
        return 0


class OperatingProfile(object):
    def __init__(self, element):
        element = element

        regular_days_element = element.find('txc:RegularDayType', NS)
        days_of_week_element = regular_days_element.find('txc:DaysOfWeek', NS)
        if days_of_week_element is None:
            self.regular_days = [e.tag[33:] for e in regular_days_element]
        else:
            self.regular_days = [e.tag[33:] for e in days_of_week_element]

        # special_days_element = element.find('txc:RegularDayType', NS)

    def __str__(self):
        if len(self.regular_days) == 1:
            if 'To' in self.regular_days[0]:
                return self.regular_days[0].replace('To', ' to ')
            return self.regular_days[0] + 's'

        string = 's, '.join(self.regular_days[:-1]) + 's and ' + self.regular_days[-1] + 's'

        if string == 'Mondays, Tuesdays, Wednesdays, Thursdays and Fridays':
            string = 'Monday to Friday'
        elif string == 'Mondays, Tuesdays, Wednesdays, Thursdays, Fridays and Saturdays':
            string = 'Monday to Saturday'
        elif string == 'Mondays, Tuesdays, Wednesdays, Thursdays, Fridays, Saturdays and Sundays':
            string = 'Monday to Sunday'
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


class DateRange(object):
    def __init__(self, element):
        self.start = datetime.strptime(element.find('txc:StartDate', NS), '%Y-%m-%d').date()
        self.end = datetime.strptime(element.find('txc:EndDate', NS), '%Y-%m-%d').date()

    def __str__(self):
        if self.start == self.end:
            return str(self.start)
        else:
            return '%s to %s' % (str(self.start), str(self.end))


class Timetable(object):
    def __init__(self, xml):
        self.outbound_grouping = Grouping('outbound')
        self.inbound_grouping = Grouping('inbound')

        stops = {
            element.find('txc:StopPointRef', NS).text: Stop(element)
            for element in xml.find('txc:StopPoints', NS)
        }
        journeypatternsections = {
            element.get('id'): JourneyPatternSection(element, stops)
            for element in xml.find('txc:JourneyPatternSections', NS)
        }
        journeypatterns = {
            element.get('id'): JourneyPattern(element, journeypatternsections, self.outbound_grouping, self.inbound_grouping)
            for element in xml.findall('.//txc:JourneyPattern', NS)
        }

        # time calculation begins here:
        journeys = {
            element.find('txc:VehicleJourneyCode', NS).text: VehicleJourney(element, journeypatterns)
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
            journey.journeypattern.grouping.journeys.append(journey)
            journey.add_times()

        self.journeypatterns = journeypatterns.values()

        self.outbound_grouping.rows = self.outbound_grouping.rows.values()
        self.outbound_grouping.rows.sort(key=Row.get_sequencenumber)
        self.inbound_grouping.rows = self.inbound_grouping.rows.values()
        self.inbound_grouping.rows.sort(key=Row.get_sequencenumber)

        service_element = xml.find('txc:Services', NS).find('txc:Service', NS)
        operatingprofile_element = service_element.find('txc:OperatingProfile', NS)
        if operatingprofile_element is not None:
            self.operating_profile = OperatingProfile(operatingprofile_element)

        self.groupings = [self.outbound_grouping, self.inbound_grouping]


def timetable_from_service(service):
    if service.region_id == 'GB':
        service.service_code = '_'.join(service.service_code.split('_')[::-1])
        archive_path = os.path.join(DIR, '../data/TNDS/NCSD.zip')
    else:
        archive_path = os.path.join(DIR, '../data/TNDS/%s.zip' % service.region_id)

    archive = zipfile.ZipFile(archive_path)
    file_names = [name for name in archive.namelist() if service.service_code in name]

    xml_file = archive.open(file_names[0])
    xml = ET.parse(xml_file).getroot()

    return Timetable(xml)

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


def runtime(string):
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
    def __init__(self, stop):
        self.stop = stop
        self.times = []


class JourneyPattern(object):
    def __init__(self, element, sections):
        self.direction = element.find('txc:Direction', NS).text
        self.sections = [
            sections[section_element.text]
            for section_element in element.findall('txc:JourneyPatternSectionRefs', NS)
        ]
        self.rows = [
            Row(self.sections[0].timinglinks[0].from_stop)
        ]
        for section in self.sections:
            for timinglink in section.timinglinks:
                self.rows.append(Row(timinglink.to_stop))
        self.element = element

    def get_departure_time(self):
        return self.rows[0].times[0]

    def __str__(self):
        return '%s to %s' % (self.rows[0].stop, self.rows[-1].stop)


class JourneyPatternSection(object):
    def __init__(self, element, stops):
        self.timinglinks = [
            JourneyPatternTimingLink(timinglink_element, stops)
            for timinglink_element in element
        ]


class JourneyPatternTimingLink(object):
    def __init__(self, element, stops):
        from_element = element.find('txc:From', NS)
        # self.from_activity = from_element.find('txc:Activity', NS).text
        self.from_stop = stops[from_element.find('txc:StopPointRef', NS).text]
        self.from_timingstatus = from_element.find('txc:TimingStatus', NS).text

        to_element = element.find('txc:To', NS)
        # self.to_activity = to_element.find('txc:Activity', NS).text
        self.to_stop = stops[to_element.find('txc:StopPointRef', NS).text]
        self.to_timingstatus = to_element.find('txc:TimingStatus', NS).text

        self.runtime = runtime(element.find('txc:RunTime', NS).text)


class VehicleJourney(object):
    def __init__(self, element, journeypatterns):
        self.departure_time = datetime.strptime(
            element.find('txc:DepartureTime', NS).text, '%H:%M:%S'
        ).time()

        journeypatternref_element = element.find('txc:JourneyPatternRef', NS)
        if journeypatternref_element is not None:
            self.set_journeypattern(
                journeypatterns.get(
                    journeypatternref_element.text
                )
            )
        else:
            # Journey has no direct reference to a JourneyPattern, will set later
            self.journeyref = element.find('txc:VehicleJourneyRef', NS).text

    def set_journeypattern(self, journeypattern):
        journeypattern.rows[0].times.append(self.departure_time)
        i = 1
        for section in journeypattern.sections:
            for timinglink in section.timinglinks:
                journeypattern.rows[i].times.append(
                    (datetime.combine(date.today(), journeypattern.rows[i-1].times[-1]) + timinglink.runtime).time()
                )
                i += 1
        self.journeypattern = journeypattern

    def __str__(self):
        return '%s to %s' % (self.rows[0].stop, self.rows[-1].stop)


class Timetable(object):

    def __init__(self, service):
        # now = datetime.today()

        if service.region_id == 'GB':
            service.service_code = '_'.join(service.service_code.split('_')[::-1])
            archive_path = os.path.join(DIR, '../data/TNDS/NCSD.zip')
        else:
            archive_path = os.path.join(DIR, '../data/TNDS/%s.zip' % service.region_id)

        archive = zipfile.ZipFile(archive_path)
        file_names = [name for name in archive.namelist() if service.service_code in name]

        xml_file = archive.open(file_names[0])
        xml = ET.parse(xml_file).getroot()

        self.stops = {
            element.find('txc:StopPointRef', NS).text: Stop(element)
            for element in xml.find('txc:StopPoints', NS)
        }
        self.journeypatternsections = {
            element.get('id'): JourneyPatternSection(element, self.stops)
            for element in xml.find('txc:JourneyPatternSections', NS)
        }
        self.journeypatterns = {
            element.get('id'): JourneyPattern(element, self.journeypatternsections)
            for element in xml.findall('.//txc:JourneyPattern', NS)
        }
        self.journeys = {
            element.find('txc:VehicleJourneyCodeVehicleJourney', NS): VehicleJourney(element, self.journeypatterns)
            for element in xml.find('txc:VehicleJourneys', NS)
        }
        for journey in self.journeys:
            if hasattr(journey, 'journeyref'):
                journey.set_journeypattern(
                    self.journeys[journey.journeyref]
                )

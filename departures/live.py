"""Various ways of getting live departures from some web service"""
import re
import datetime

import requests
import pytz
import dateutil.parser
from bs4 import BeautifulSoup
from django.conf import settings
from django.utils.text import slugify
from busstops.models import Operator, StopUsageUsage


STAGECOACH_OPERATORS = (
    'CLTL', 'ELBG', 'NFKG', 'SBLB', 'SCBD', 'SCBL', 'SCCM', 'SCCO', 'SCCU',
    'SCEB', 'SCEK', 'SCFI', 'SCGL', 'SCGR', 'SCHA', 'SCHM', 'SCHT', 'SCHU',
    'SCHW', 'SCLI', 'SCMB', 'SCMN', 'SCMY', 'SCNE', 'SCNH', 'SCNW', 'SCOR',
    'SCOX', 'SCST', 'SCTE', 'SCWW', 'SDVN', 'SINV', 'SLAN', 'SMSO', 'SSPH',
    'SSTY', 'SSWL', 'SSWN', 'STCR', 'STGS', 'STLA', 'STWS', 'SYRK', 'YSYC',
)
DESTINATION_REGEX = re.compile(r'.+\((.+)\)')
LOCAL_TIMEZONE = pytz.timezone('Europe/London')
SESSION = requests.Session()


class Departures(object):
    """Abstract class for getting departures from a source"""
    def __init__(self, stop, services):
        self.stop = stop
        self.services = {
            service.line_name.split('|', 1)[0].lower(): service
            for service in services
        }

    def get_request_url(self):
        """Return a URL string to pass to get_response"""
        raise NotImplementedError

    def get_request_params(self):
        """Return a dictionary of HTTP GET parameters"""
        return None

    def get_response(self):
        return SESSION.get(self.get_request_url(), params=self.get_request_params())

    def get_service(self, line_name):
        """Given a line name string, returns the Service matching a line name
        (case-insensitively), or a line name string
        """
        return self.services.get(line_name.lower(), line_name)

    def departures_from_response(self, res):
        """Given a Response object from the requests module,
        returns a list of departures
        """
        raise NotImplementedError

    def get_departures(self):
        """Returns a list of departures"""
        return self.departures_from_response(self.get_response())


class TflDepartures(Departures):
    """Departures from the Transport for London API"""
    def get_request_url(self):
        return 'http://api.tfl.gov.uk/StopPoint/%s/arrivals' % self.stop.pk

    def departures_from_response(self, res):
        rows = res.json()
        if rows:
            name = rows[0]['stationName']
            heading = int(rows[0]['bearing'])
            if name != self.stop.common_name or heading != self.stop.heading:
                self.stop.common_name = name
                self.stop.heading = heading
                self.stop.save()
        return ({
            'time': dateutil.parser.parse(item.get('expectedArrival')).astimezone(LOCAL_TIMEZONE),
            'service': self.get_service(item.get('lineName')),
            'destination': item.get('destinationName'),
        } for item in res.json())


class AcisDepartures(Departures):
    """Departures from a website ending in .acisconnect.com or .acislive.com"""
    def __init__(self, prefix, stop, services):
        self.prefix = prefix
        super(AcisDepartures, self).__init__(stop, services)


class AcisLiveDepartures(AcisDepartures):
    """Departures from an old-fashioned website ending in .acislive.com"""
    def get_request_url(self):
        return 'http://%s.acislive.com/pip/stop_simulator_table.asp' % self.prefix

    def get_request_params(self):
        return {
            'naptan': self.stop.naptan_code
        }

    def departures_from_response(self, res):
        soup = BeautifulSoup(res.text, 'lxml')
        cells = [cell.text.strip() for cell in soup.find_all('td')]
        rows = (cells[i * 4 - 4:i * 4] for i in range(1, int(len(cells) / 4) + 1))
        return ({
            'time': row[2],
            'service': self.get_service(row[0]),
            'destination': row[1]
        } for row in rows)


class AcisConnectDepartures(AcisDepartures):
    """Departures from a website ending in '.acisconnect.com'"""
    @staticmethod
    def get_time(cell):
        """Given a Beautiful Soup element, returns its text made nicer
        ('1 Mins' becomes '1 min', '2 Mins' becomes '2 mins')
        """
        text = cell.text
        if text == '1 Mins':
            return '1 min'
        return text.replace('Mins', 'mins')

    def get_request_url(self):
        return 'http://%s.acisconnect.com/Text/WebDisplay.aspx' % self.prefix

    def get_request_params(self):
        return {
            'stopRef': self.stop.naptan_code if self.prefix == 'yorkshire' else self.stop.pk
        }

    def departures_from_response(self, res):
        soup = BeautifulSoup(res.text, 'lxml')
        table = soup.find(id='GridViewRTI')
        if table is None:
            return
        rows = (row.findAll('td') for row in table.findAll('tr')[1:])
        if self.prefix == 'yorkshire':
            return ({
                'time': self.get_time(row[2]),
                'service': self.get_service(row[0].text),
                'destination': row[1].text
            } for row in rows)
        else:
            return ({
                'time': self.get_time(row[4]),
                'service': self.get_service(row[0].text),
                'destination': row[2].text
            } for row in rows)


class TransportApiDepartures(Departures):
    """Departures from Transport API"""
    def __init__(self, stop, services, today):
        self.today = today
        super(TransportApiDepartures, self).__init__(stop, services)

    @staticmethod
    def _get_destination(item):
        destination = item['direction']
        destination_matches = DESTINATION_REGEX.match(destination)
        if destination_matches is not None:
            destination = destination_matches.groups()[0]
        elif item['source'] == 'VIX' and ',' in destination:
            destination = destination.split(',', 1)[0]
        return destination

    def get_row(self, item):
        time = item['best_departure_estimate']
        if time is None:
            return
        hour = int(time[:2])
        while hour > 23:
            hour -= 24
            time = '%s%s' % (hour, time[2:])
        departure_time = None
        if item.get('date') is not None:
            departure_time = dateutil.parser.parse(item['date'] + ' ' + time)
            if (item['source'].startswith('Traveline timetable') and
                    departure_time.date() > self.today):
                return
        if departure_time is None:
            departure_time = datetime.datetime.combine(
                self.today, dateutil.parser.parse(time).time()
            )
        return {
            'time': departure_time,
            'service': self.get_service(item.get('line').split('--', 1)[0].split('|', 1)[0]),
            'destination': self._get_destination(item),
        }

    def get_request_url(self):
        return 'http://transportapi.com/v3/uk/bus/stop/%s/live.json' % self.stop.atco_code

    def get_request_params(self):
        return {
            'app_id': settings.TRANSPORTAPI_APP_ID,
            'app_key': settings.TRANSPORTAPI_APP_KEY,
            'nextbuses': 'no',
            'group': 'no',
        }

    def departures_from_response(self, res):
        departures = res.json().get('departures')
        if departures and 'all' in departures:
            return [row for row in map(self.get_row, departures['all']) if row]


class TimetableDepartures(Departures):
    def __init__(self, stop, services, now):
        self.now = now
        super(TimetableDepartures, self).__init__(stop, services)

    def get_departures(self):
        queryset = StopUsageUsage.objects.filter(datetime__gte=self.now, stop=self.stop).order_by('datetime')
        return [{
            'time': suu.datetime,
            'destination': suu.journey.destination.locality,
            'service': suu.journey.service
        } for suu in queryset.select_related('stop', 'journey__destination__locality', 'journey__service')[:10]]


class StagecoachDepartures(Departures):
    def __init__(self, stop, services, now):
        self.now = now
        super(StagecoachDepartures, self).__init__(stop, services)

    def get_response(self):
        return SESSION.post(
            'https://api.stagecoachbus.com/tis/v3/stop-event-query',
            headers={
                'Origin': 'https://www.stagecoachbus.com',
                'Referer': 'https://www.stagecoachbus.com',
                'X-SC-apiKey': 'ukbusprodapi_9T61Jo3vsbql#!',
                'X-SC-securityMethod': 'API'
            },
            json={
                'Stops': {
                    'StopLabel': (self.stop.atco_code,)
                },
                'Departure': {
                    'TargetDepartureTime': {
                        'value': self.now.isoformat()
                    }
                },
                'ResponseCharacteristics': {
                    'MaxLaterEvents': {
                        'value': 20
                    }
                },
                'RequestId': 'bus-stop-query-stagecoach'
            }
        )

    def get_row(self, row):
        service = row['Trip']['Service']['ServiceNumber']
        return {
            'time': dateutil.parser.parse(row['ScheduledDepartureTime']['value']),
            'destination': row['Trip'].get('DestinationBoard') or row['Trip'].get('Description'),
            'service': self.services.get(service.lower(), service)
        }

    def departures_from_response(self, response):
        events = response.json().get('Events')
        if events:
            return [self.get_row(event) for event in events.get('Event')]


def get_max_age(departures, now):
    """Given a list of departures and the current datetime, returns an
    appropriate max_age in seconds (for use in a cache-control header)
    (for costly Transport API departures)
    """
    if departures is not None:
        if len(departures) > 0:
            expiry = departures[0]['time']
            if now < expiry:
                return (expiry - now).seconds + 60
            return 60
        midnight = datetime.datetime.combine(
            now.date() + datetime.timedelta(days=1), datetime.time(0)
        )
        return (midnight - now).seconds
    return 3600


def get_departures(stop, services):
    """Given a StopPoint object and an iterable of Service objects,
    returns a tuple containing a context dictionary and a max_age integer
    """
    live_sources = stop.live_sources.values_list('name', flat=True)

    # Transport for London
    if 'TfL' in live_sources:
        departures = TflDepartures(stop, services)
        return ({
            'departures': departures,
            'today': datetime.date.today(),
            'source': {
                # use departures.stop instead of local stop,
                # in case it was updated in departures_from_response
                'url': 'https://tfl.gov.uk/bus/stop/%s/%s' % (departures.stop.atco_code,
                                                              slugify(departures.stop.common_name)),
                'name': 'Transport for London'
            }
        }, 60)

    now = datetime.datetime.now()

    # Stagecoach
    operators = Operator.objects.filter(service__stops=stop,
                                        service__current=True).distinct().values_list('pk', flat=True)
    if operators and all(operator in STAGECOACH_OPERATORS for operator in operators):
        departures = StagecoachDepartures(stop, services, now).get_departures()
        return ({
            'departures': departures
        }, 120)  # get_max_age(departures, now))

    # Yorkshire
    if 'Y' in live_sources:
        return ({
            'departures': AcisConnectDepartures('yorkshire', stop, services),
            'source': {
                'url': 'http://yorkshire.acisconnect.com/Text/WebDisplay.aspx?stopRef=%s' % stop.naptan_code,
                'name': 'Your Next Bus'
            }
        }, 60)

    # Kent
    if 'Kent' in live_sources:
        return ({
            'departures': AcisLiveDepartures('kent', stop, services),
            'source': {
                'url': 'http://%s.acislive.com/pip/stop_simulator.asp?NaPTAN=%s' % ('kent', stop.naptan_code),
                'name': 'ACIS Live'
            }
        }, 60)

    for live_source_name, prefix in (
            ('ayr', 'ayrshire'),
            ('west', 'travelwest'),
            ('buck', 'buckinghamshire'),
            ('camb', 'cambridgeshire'),
            ('aber', 'aberdeen'),
            ('card', 'cardiff'),
            ('swin', 'swindon'),
            ('metr', 'metrobus')
    ):
        if live_source_name in live_sources:
            return ({
                'departures': AcisConnectDepartures(prefix, stop, services),
                'source': {
                    'url': 'http://%s.acisconnect.com/Text/WebDisplay.aspx?stopRef=%s' % (prefix, stop.pk),
                    'name': 'vixConnect'
                }
            }, 60)

    # Belfast
    if stop.pk.startswith('7000000'):
        return ({
            'departures': AcisConnectDepartures('belfast', stop, services),
            'source': {
                'url': 'http://belfast.acisconnect.com/Text/WebDisplay.aspx?stopRef=%s' % stop.pk,
                'name': 'vixConnect'
            }
        }, 60)

    # Norfolk
    if stop.atco_code.startswith('290'):
        departures = TimetableDepartures(stop, (), now).get_departures()
        return ({
            'departures': departures,
            'today': now.date(),
        },  60)

    # Transport API
    departures = TransportApiDepartures(stop, services, now.date()).get_departures()
    return ({
        'departures': departures,
        'source': {
            'url': 'http://www.transportapi.com/',
            'name': 'Transport API',
        }
    }, get_max_age(departures, now))

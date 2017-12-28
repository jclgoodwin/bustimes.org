"""Various ways of getting live departures from some web service"""
import re
import datetime
import requests
import pytz
import dateutil.parser
from bs4 import BeautifulSoup
from django.conf import settings
from django.utils.text import slugify
from django.utils.timezone import make_naive
from busstops.models import Operator, Service


DESTINATION_REGEX = re.compile(r'.+\((.+)\)')
LOCAL_TIMEZONE = pytz.timezone('Europe/London')
SESSION = requests.Session()


class Departures(object):
    """Abstract class for getting departures from a source"""
    def __init__(self, stop, services, now=None):
        self.stop = stop
        self.now = now
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
        try:
            response = self.get_response()
        except requests.exceptions.ConnectionError:
            return
        if response.ok:
            return self.departures_from_response(response)


class TflDepartures(Departures):
    """Departures from the Transport for London API"""
    def get_request_url(self):
        return 'https://api.tfl.gov.uk/StopPoint/%s/arrivals' % self.stop.pk

    def departures_from_response(self, res):
        rows = res.json()
        if rows:
            name = rows[0]['stationName']
            heading = int(rows[0]['bearing'])
            if name != self.stop.common_name or heading != self.stop.heading:
                self.stop.common_name = name
                self.stop.heading = heading
                self.stop.save()
        return sorted([{
            'live': dateutil.parser.parse(item.get('expectedArrival')).astimezone(LOCAL_TIMEZONE),
            'service': self.get_service(item.get('lineName')),
            'destination': item.get('destinationName'),
        } for item in res.json()], key=lambda d: d['live'])


class AcisDepartures(Departures):
    """Departures from a website ending in .acisconnect.com or .acislive.com"""
    def get_time(self, text):
        if 'min' in text.lower():
            return (None, self.now + datetime.timedelta(minutes=int(text.split(' ', 1)[0])))
        if text == 'Due':
            return (None, self.now)
        return (text, None)

    def __init__(self, prefix, stop, services, now):
        self.prefix = prefix
        super(AcisDepartures, self).__init__(stop, services, now)


class AcisLiveDepartures(AcisDepartures):
    """Departures from an old-fashioned website ending in .acislive.com"""
    def get_request_url(self):
        return 'http://%s.acislive.com/pip/stop_simulator_table.asp' % self.prefix

    def get_request_params(self):
        return {
            'naptan': self.stop.naptan_code
        }

    def get_row(self, row):
        time, live = self.get_time(row[2])
        return {
            'time': time,
            'live': live,
            'service': self.get_service(row[0]),
            'destination': row[1]
        }

    def departures_from_response(self, res):
        soup = BeautifulSoup(res.text, 'lxml')
        cells = [cell.text.strip() for cell in soup.find_all('td')]
        rows = (cells[i * 4 - 4:i * 4] for i in range(1, int(len(cells) / 4) + 1))
        return [self.get_row(row) for row in rows]


class AcisConnectDepartures(AcisDepartures):
    """Departures from a website ending in '.acisconnect.com'"""
    def get_request_url(self):
        return 'http://%s.acisconnect.com/Text/WebDisplay.aspx' % self.prefix

    def get_request_params(self):
        return {
            'stopRef': self.stop.naptan_code if self.prefix == 'yorkshire' else self.stop.pk
        }

    def get_yorkshire_row(self, row):
        time, live = self.get_time(row[2].text)
        return {
            'time': time,
            'live': live,
            'service': self.get_service(row[0].text),
            'destination': row[1].text
        }

    def get_row(self, row):
        time, live = self.get_time(row[4].text)
        return {
            'time': time,
            'live': live,
            'service': self.get_service(row[0].text),
            'destination': row[2].text
        }

    def departures_from_response(self, res):
        soup = BeautifulSoup(res.text, 'lxml')
        table = soup.find(id='GridViewRTI')
        if table is None:
            return
        rows = (row.findAll('td') for row in table.findAll('tr')[1:])
        if self.prefix == 'yorkshire':
            return [self.get_yorkshire_row(row) for row in rows]
        return [self.get_row(row) for row in rows]


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

    @staticmethod
    def _get_time(string):
        if string:
            hour = int(string[:2])
            while hour > 23:
                hour -= 24
                string = '%s%s' % (hour, string[2:])
        return string

    def get_row(self, item):
        live_time = self._get_time(item.get('expected_departure_time'))
        time = self._get_time(item['aimed_departure_time'])
        if not time:
            time = live_time
        if not time:
            return
        if item.get('date') is not None:
            time = dateutil.parser.parse(item['date'] + ' ' + time)
            if live_time:
                live_time = dateutil.parser.parse(item['date'] + ' ' + live_time)
            if (item['source'].startswith('Traveline timetable') and
                    time.date() > self.today):
                return
        else:
            time = datetime.datetime.combine(
                self.today, dateutil.parser.parse(time).time()
            )
            if live_time:
                live_time = datetime.datetime.combine(
                    self.today, dateutil.parser.parse(live_time).time()
                )
        return {
            'time': time,
            'live': live_time,
            'service': self.get_service(item.get('line').split('--', 1)[0].split('|', 1)[0]),
            'destination': self._get_destination(item),
        }

    def get_request_url(self):
        return 'http://transportapi.com/v3/uk/bus/stop/%s/live.json' % self.stop.atco_code

    def get_request_params(self):
        return {
            'app_id': settings.TRANSPORTAPI_APP_ID,
            'app_key': settings.TRANSPORTAPI_APP_KEY,
            'group': 'no',
        }

    def departures_from_response(self, res):
        departures = res.json().get('departures')
        if departures and 'all' in departures:
            return [row for row in map(self.get_row, departures['all']) if row]


class TimetableDepartures(Departures):
    @staticmethod
    def get_row(suu):
        destination = suu.journey.destination
        return {
            'time': suu.datetime.astimezone(LOCAL_TIMEZONE),
            'destination': destination.locality or destination.town or destination,
            'service': suu.journey.service
        }

    def get_departures(self):
        queryset = self.stop.stopusageusage_set.filter(datetime__gte=self.now, journey__service__current=True)
        queryset = queryset.select_related('journey__destination__locality', 'journey__service')
        queryset = queryset.defer('journey__destination__latlong', 'journey__destination__locality__latlong',
                                  'journey__service__geometry')[:10]
        return [self.get_row(suu) for suu in queryset]


class LambdaDepartures(Departures):
    def get_request_url(self):
        return 'https://api.bustim.es/' + self.stop.atco_code

    def departures_from_response(self, res):
        json = res.json()
        if 'departures' in json:
            return [{
                'time': dateutil.parser.parse(item['aimed_time']),
                'live': item['expected_time'] and dateutil.parser.parse(item['expected_time']),
                'service': self.get_service(item['service']),
                'destination': item['destination_name']
            } for item in json['departures'] if item['aimed_time']]


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


def add_stagecoach_departures(stop, services_dict, departures):
    headers = {
        'Origin': 'https://www.stagecoachbus.com',
        'Referer': 'https://www.stagecoachbus.com',
        'X-SC-apiKey': 'ukbusprodapi_9T61Jo3vsbql#!',
        'X-SC-securityMethod': 'API'
    }
    json = {
        'StopMonitorRequest': {
            'header': {
                'retailOperation': '',
                'channel': '',
            },
            'stopMonitorQueries': {
                'stopMonitorQuery': [{
                    'stopPointLabel': stop.atco_code,
                    'servicesFilters': {}
                }]
            }
        }
    }
    try:
        response = SESSION.post('https://api.stagecoachbus.com/adc/stop-monitor', headers=headers, json=json)
    except requests.exceptions.ConnectionError:
        return departures
    if not response.ok:
        return departures
    stop_monitors = response.json()['stopMonitors']
    if 'stopMonitor' in stop_monitors:
        added = False
        for monitor in stop_monitors['stopMonitor'][0]['monitoredCalls']['monitoredCall']:
            if 'expectedDepartureTime' in monitor:
                aimed, expected = [dateutil.parser.parse(time).astimezone(LOCAL_TIMEZONE)
                                   for time in (monitor['aimedDepartureTime'], monitor['expectedDepartureTime'])]
                line = monitor['lineRef']
                if aimed >= departures[0]['time']:
                    replaced = False
                    for departure in departures:
                        if aimed == departure['time']:
                            departure['live'] = expected
                            replaced = True
                            break
                    if replaced:
                        continue
                    for departure in departures:
                        if not departure.get('live') and line == departure['service'].line_name:
                            departure['live'] = expected
                            replaced = True
                            break
                    if replaced:
                        continue
                departures.append({
                    'time': aimed,
                    'live': expected,
                    'service': services_dict.get(line.lower(), line),
                    'destination': monitor['destinationDisplay']
                })
                added = True
        if added:
            departures.sort(key=lambda d: d['time'])
    return departures


def services_match(a, b):
    if type(a) == Service:
        a = a.line_name
    if type(b) == Service:
        b = b.line_name
    return a == b


def can_sort(departure):
    return type(departure['time']) is datetime or type(departure['live']) is datetime


def get_departure_order(departure):
    if departure['time']:
        if departure['time'].tzinfo:
            return make_naive(departure['time'])
        return departure['time']
    return make_naive(departure['live'])


def blend(departures, live_rows):
    added = False
    for live_row in live_rows:
        replaced = False
        for row in departures:
            if (
                services_match(row['service'], live_row['service'])
                and (
                    row['time'] and row['time'] == live_row['time']
                    or 'live' not in row and (
                        live_row['time'] is None
                        or type(live_row['time']) is str
                        or make_naive(row['time']) <= live_row['time']
                    )
                )
            ):
                row['live'] = live_row['live']
                replaced = True
                break
        if not replaced:
            added = True
            departures.append(live_row)
    if added and all(can_sort(departure) for departure in departures):
        departures.sort(key=get_departure_order)


def get_departures(stop, services, bot=False):
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

    now = datetime.datetime.now(LOCAL_TIMEZONE)

    # Yorkshire
    if 'Y' in live_sources:
        return ({
            'departures': AcisConnectDepartures('yorkshire', stop, services, now),
            'source': {
                'url': 'http://yorkshire.acisconnect.com/Text/WebDisplay.aspx?stopRef=%s' % stop.naptan_code,
                'name': 'Your Next Bus'
            }
        }, 60)

    # Kent
    if 'Kent' in live_sources:
        return ({
            'departures': AcisLiveDepartures('kent', stop, services, now),
            'source': {
                'url': 'http://%s.acislive.com/pip/stop_simulator.asp?NaPTAN=%s' % ('kent', stop.naptan_code),
                'name': 'ACIS Live'
            }
        }, 60)

    operators = Operator.objects.filter(service__stops=stop,
                                        service__current=True).distinct()

    # Dublin
    if stop.atco_code[0] == '8' and 'DB' in stop.atco_code:
        try:
            response = SESSION.get(
                'https://data.dublinked.ie/cgi-bin/rtpi/realtimebusinformation',
                params={'stopid': int(stop.atco_code.split('DB', 1)[-1])}
            )
        except requests.exceptions.ConnectionError:
            pass
        if response.ok:
            services_dict = {service.line_name.lower(): service for service in services}
            departures = [{
                'time': dateutil.parser.parse(item['scheduleddeparturedatetime'], dayfirst=True),
                'live': dateutil.parser.parse(item['departuredatetime'], dayfirst=True),
                'destination': item['destination'],
                'service': services_dict.get(item['route'].lower(), item['route'])
            } for item in response.json()['results']]
            return ({
                'departures': departures
            }, 60)

    departures = TimetableDepartures(stop, services, now)
    services_dict = departures.services
    departures = departures.get_departures()

    if not departures or (departures[0]['time'] - now) < datetime.timedelta(hours=1):
        # Stagecoach
        if any(operator.name.startswith('Stagecoach') for operator in operators):
            if departures:
                departures = add_stagecoach_departures(stop, services_dict, departures)
        else:
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
                    live_rows = AcisConnectDepartures(prefix, stop, services, now).get_departures()
                    if live_rows:
                        blend(departures, live_rows)

                    return ({
                        'departures': departures,
                        'today': now.date(),
                        'source': {
                            'url': 'http://%s.acisconnect.com/Text/WebDisplay.aspx?stopRef=%s' % (prefix, stop.pk),
                            'name': 'vixConnect'
                        }
                    }, 60)
        # Belfast
        if operators and any(operator.id == 'MET' for operator in operators):
            live_rows = AcisConnectDepartures('belfast', stop, services, now).get_departures()
            if live_rows:
                blend(departures, live_rows)
        # Norfolk
        elif not bot and departures and stop.atco_code[:3] == '290':
            live_rows = LambdaDepartures(stop, services, now).get_departures()
            if live_rows:
                blend(departures, live_rows)

    return ({
        'departures': departures,
        'today': now.date(),
    },  60)

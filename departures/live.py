"""Various ways of getting live departures from some web service"""
import re
import ciso8601
import datetime
import requests
import pytz
import dateutil.parser
import logging
from bs4 import BeautifulSoup
from django.conf import settings
from django.utils.timezone import is_naive, make_naive
from busstops.models import Operator, Service, StopPoint, ServiceCode


logger = logging.getLogger(__name__)
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
        pass

    def get_request_headers(self):
        """Return a dictionary of HTTP headers"""
        pass

    def get_request_kwargs(self):
        return {
            'params': self.get_request_params(),
            'headers': self.get_request_headers(),
            'timeout': 10
        }

    def get_response(self):
        return SESSION.get(self.get_request_url(), **self.get_request_kwargs())

    def get_service(self, line_name):
        """Given a line name string, returns the Service matching a line name
        (case-insensitively), or a line name string
        """
        if line_name:
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
        except requests.exceptions.ReadTimeout:
            return
        except requests.exceptions.RequestException as e:
            logger.error(e, exc_info=True)
            return
        if response.ok:
            return self.departures_from_response(response)


class DublinDepartures(Departures):
    def get_request_url(self):
        return 'https://data.dublinked.ie/cgi-bin/rtpi/realtimebusinformation'

    def get_request_params(self):
        return {
            'stopid': int(self.stop.atco_code.split('DB', 1)[-1])
        }

    def departures_from_response(self, response):
        return [{
            'time': dateutil.parser.parse(item['scheduleddeparturedatetime'], dayfirst=True),
            'live': dateutil.parser.parse(item['departuredatetime'], dayfirst=True),
            'destination': item['destination'],
            'service': self.get_service(item['route'])
        } for item in response.json()['results']]


class SingaporeDepartures(Departures):
    def get_request_url(self):
        return 'http://datamall2.mytransport.sg/ltaodataservice/BusArrivalv2'

    def get_request_params(self):
        return {
            'BusStopCode': self.stop.atco_code[3:]
        }

    def get_request_headers(self):
        return {
            'AccountKey': settings.SINGAPORE_KEY
        }

    def departures_from_response(self, response):
        departures = []
        for service_response in response.json()['Services']:
            service = self.get_service(service_response['ServiceNo'])
            key = 'NextBus'
            i = 1
            while key in service_response:
                item = service_response[key]
                if not item['EstimatedArrival']:
                    break
                departures.append({
                    'live': ciso8601.parse_datetime(item['EstimatedArrival']),
                    'destination': item['DestinationCode'],
                    'service': service
                })
                i += 1
                key = 'NextBus{}'.format(i)
        destinations = StopPoint.objects.in_bulk(['sg-' + departure['destination'] for departure in departures])
        for departure in departures:
            departure['destination'] = destinations.get('sg-' + departure['destination'], '')
        return departures


class JerseyDepartures(Departures):
    def get_request_url(self):
        return 'http://sojbuslivetimespublic.azurewebsites.net/api/Values/v1/BusStop/' + self.stop.atco_code[3:]

    def departures_from_response(self, response):
        departures = []
        for item in response.json():
            time = ciso8601.parse_datetime(item['ETA'])
            row = {
                'time': time,
                'destination': item['Destination'],
                'service': self.get_service(item['ServiceNumber'])
            }
            if item['IsTracked']:
                row['live'] = time
            departures.append(row)
        return departures


class TflDepartures(Departures):
    """Departures from the Transport for London API"""
    @staticmethod
    def get_request_params():
        return settings.TFL

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
            'live': parse_datetime(item.get('expectedArrival')),
            'service': self.get_service(item.get('lineName')),
            'destination': item.get('destinationName'),
        } for item in rows], key=lambda d: d['live'])


class WestMidlandsDepartures(Departures):
    @staticmethod
    def get_request_params():
        return {
            **settings.TFWM,
            'formatter': 'json'
        }

    def get_request_url(self):
        return 'http://api.tfwm.org.uk/stoppoint/%s/arrivals' % self.stop.pk

    def departures_from_response(self, res):
        return sorted([{
            'time': ciso8601.parse_datetime(item['ScheduledArrival']),
            'live': ciso8601.parse_datetime(item['ExpectedArrival']),
            'service': self.get_service(item['LineName']),
            'destination': item['DestinationName'],
        } for item in res.json()['Predictions']['Prediction'] if item['ExpectedArrival']], key=lambda d: d['live'])


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
        super().__init__(stop, services, now)


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

    def get_row(self, row):
        time, live = self.get_time(row[-2].text)
        return {
            'time': time,
            'live': live,
            'service': self.get_service(row[0].text),
            'destination': row[1].text if len(row) == 4 else row[2].text
        }

    def departures_from_response(self, res):
        soup = BeautifulSoup(res.text, 'lxml')
        table = soup.find(id='GridViewRTI')
        if table is None:
            return
        rows = (row.findAll('td') for row in table.findAll('tr')[1:])
        return [self.get_row(row) for row in rows]


class TransportApiDepartures(Departures):
    """Departures from Transport API"""
    def __init__(self, stop, services, today):
        self.today = today
        super().__init__(stop, services)

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
                string = '%02d%s' % (hour, string[2:])
        return string

    def get_row(self, item):
        live_time = self._get_time(item.get('expected_departure_time'))
        time = self._get_time(item['aimed_departure_time'])
        if not time:
            time = live_time
        if not time:
            return
        if item.get('date') is not None:
            time = ciso8601.parse_datetime(item['date'] + ' ' + time)
            if live_time:
                live_time = ciso8601.parse_datetime(item['date'] + ' ' + live_time)
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
            **settings.TRANSPORTAPI,
            'group': 'no'
        }

    def departures_from_response(self, res):
        departures = res.json().get('departures')
        if departures and 'all' in departures:
            return [row for row in map(self.get_row, departures['all']) if row]


class UKTrainDepartures(Departures):
    def get_request_url(self):
        return 'http://transportapi.com/v3/uk/train/station/tiploc:%s/live.json' % self.stop.atco_code[4:]

    def get_request_params(self):
        return settings.TRANSPORTAPI

    @staticmethod
    def get_time(res, item, key):
        if item[key]:
            return ciso8601.parse_datetime(res['date'] + ' ' + item[key])
        if item['status'] == 'CANCELLED':
            return 'Cancelled'

    def departures_from_response(self, res):
        res = res.json()
        return [{
            'time': self.get_time(res, item, 'aimed_departure_time'),
            'live': self.get_time(res, item, 'expected_departure_time'),
            'service': item['operator_name'],
            'destination': item['destination_name']
        } for item in res['departures']['all']]


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


def parse_datetime(string):
    return ciso8601.parse_datetime(string).astimezone(LOCAL_TIMEZONE)


class LambdaDepartures(Departures):
    def get_request_url(self):
        return 'https://api.bustim.es/' + self.stop.atco_code

    def get_row(self, item):
        row = {
            'time': parse_datetime(item['aimed_time']),
            'live': item['expected_time'],
            'service': self.get_service(item['service']),
            'destination': item['destination_name']
        }
        if row['live']:
            row['live'] = parse_datetime(row['live'])
        if self.stop.atco_code[:3] == '290':
            row['line'] = item.get('line')
        return row

    def departures_from_response(self, res):
        json = res.json()
        if 'departures' in json:
            return [self.get_row(item) for item in json['departures'] if item['aimed_time']]


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
        response = SESSION.post('https://api.stagecoachbus.com/adc/stop-monitor',
                                headers=headers, json=json, timeout=2)
    except requests.exceptions.RequestException as e:
        logger.error(e, exc_info=True)
        return departures
    if not response.ok:
        return departures
    stop_monitors = response.json()['stopMonitors']
    if 'stopMonitor' in stop_monitors:
        added = False
        for monitor in stop_monitors['stopMonitor'][0]['monitoredCalls']['monitoredCall']:
            if 'expectedDepartureTime' in monitor:
                aimed, expected = [parse_datetime(time)
                                   for time in (monitor['aimedDepartureTime'], monitor['expectedDepartureTime'])]
                line = monitor['lineRef']
                if aimed >= departures[0]['time']:
                    replaced = False
                    for departure in departures:
                        if aimed == departure['time']:
                            if type(departure['service']) is Service and line == departure['service'].line_name:
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
    return type(departure['time']) is datetime.datetime or type(departure.get('live')) is datetime.datetime


def get_departure_order(departure):
    if departure['time']:
        if is_naive(departure['time']):
            return departure['time']
        return make_naive(departure['time'])
    return make_naive(departure['live'])


def blend(departures, live_rows, stop=None):
    added = False
    for live_row in live_rows:
        replaced = False
        for row in departures:
            if (
                services_match(row['service'], live_row['service']) and
                row['time'] and row['time'] == live_row['time']
            ):
                row['live'] = live_row['live']
                if live_row.get('line') and type(row['service']) is Service:
                    if live_row['line'] != row['service'].line_name:
                        ServiceCode.objects.update_or_create({'code': live_row['line']},
                                                             service=row['service'], scheme='NCC Hogia')
                replaced = True
                break
        if not replaced:
            departures.append(live_row)
            added = True
    if added and all(can_sort(departure) for departure in departures):
        departures.sort(key=get_departure_order)


def get_departures(stop, services, bot=False):
    """Given a StopPoint object and an iterable of Service objects,
    returns a tuple containing a context dictionary and a max_age integer
    """

    # 🚂
    if stop.atco_code[:3] == '910':
        departures = UKTrainDepartures(stop, services)
        return ({
            'departures': departures,
            'source': 'Network Rail'
        }, 30)

    # Transport for London
    if stop.atco_code[:3] == '490':
        departures = TflDepartures(stop, services)
        return ({
            'departures': departures,
            'today': datetime.date.today(),
            'source': 'TfL'
        }, 60)

    # Dublin
    if stop.atco_code[0] == '8' and 'DB' in stop.atco_code:
        return ({
            'departures': DublinDepartures(stop, services).get_departures()
        }, 60)

    # Singapore
    if stop.atco_code[:3] == 'sg-':
        return ({
            'departures': SingaporeDepartures(stop, services).get_departures()
        }, 60)

    # Jersey
    if stop.atco_code[:3] == 'je-':
        return ({
            'departures': JerseyDepartures(stop, services).get_departures()
        }, 60)

    now = datetime.datetime.now(LOCAL_TIMEZONE)

    departures = TimetableDepartures(stop, services, now)
    services_dict = departures.services
    departures = departures.get_departures()

    one_hour = datetime.timedelta(hours=1)
    one_hour_ago = stop.stopusageusage_set.filter(datetime__lte=now - one_hour, journey__service__current=True)

    if not bot and (not departures or (departures[0]['time'] - now) < one_hour or one_hour_ago.exists()):

        operators = Operator.objects.filter(service__stops=stop,
                                            service__current=True).distinct()

        # Stagecoach
        if any(operator.name.startswith('Stagecoach') for operator in operators):
            if departures:
                departures = add_stagecoach_departures(stop, services_dict, departures)

        # Belfast
        if any(operator.id == 'MET' for operator in operators):
            live_rows = AcisConnectDepartures('belfast', stop, services, now).get_departures()
            if live_rows:
                blend(departures, live_rows)
        elif departures:
            if stop.atco_code[:3] == '430':
                live_rows = WestMidlandsDepartures(stop, services).get_departures()
                if live_rows:
                    blend(departures, live_rows)
            elif stop.atco_code[:3] in {
                '639', '630', '649', '607', '018', '020', '129', '038', '149', '010', '040', '050', '571', '021',
                '110', '120', '640', '618', '611', '612', '140', '150', '609', '160', '180', '190', '670', '250',
                '269', '260', '270', '029', '049', '290', '300', '617', '228', '616', '227', '019', '340', '648',
                '059', '128', '199', '039', '614', '037', '198', '619', '158', '017', '615', '390', '400', '159',
                '119', '030', '608', '440', '460', '036', '035', '200'
            } and not all(operator.name.startswith('Stagecoach') for operator in operators):
                live_rows = LambdaDepartures(stop, services, now).get_departures()
                if live_rows:
                    blend(departures, live_rows)

    if bot:
        max_age = 0
    else:
        max_age = 60

    return ({
        'departures': departures,
        'today': now.date(),
    },  max_age)

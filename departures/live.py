"""Various ways of getting live departures from some web service"""
import ciso8601
import datetime
import requests
import pytz
import logging
import xmltodict
import xml.etree.cElementTree as ET
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q, Exists, OuterRef, Value
from django.db.models.functions import Concat
from django.utils import timezone
from busstops.models import Service, ServiceCode, SIRISource
from bustimes.models import get_calendars, get_routes, Route, StopTime
from vehicles.tasks import log_vehicle_journey


logger = logging.getLogger(__name__)
LOCAL_TIMEZONE = pytz.timezone('Europe/London')


class Departures:
    """Abstract class for getting departures from a source"""
    request_url = None

    def __init__(self, stop, services, now=None):
        self.stop = stop
        self.now = now
        self.services = services
        self.services_by_name = {}
        self.services_by_alternative_name = {}
        duplicate_names = set()
        duplicate_alternative_names = set()

        for service in services:
            line_name = service.line_name.lower()
            if line_name in self.services_by_name:
                duplicate_names.add(line_name)
            else:
                self.services_by_name[line_name] = service

            service_code = service.service_code
            if '-' in service_code and '_' in service_code[2:4] and service_code[:3].islower():
                # there's sometimes an alternative abbreviated line name hidden in the service code
                parts = service_code.split('-')
                part = parts[1].lower()
                if part in self.services_by_alternative_name:
                    duplicate_alternative_names.add(part)
                elif part not in self.services_by_name:
                    self.services_by_alternative_name[part] = service

        for line_name in duplicate_names:
            del self.services_by_name[line_name]
        for line_name in duplicate_alternative_names:
            del self.services_by_alternative_name[line_name]

    def get_request_url(self):
        """Return a URL string to pass to get_response"""
        return self.request_url

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
            'timeout': 5
        }

    def get_response(self):
        return requests.get(self.get_request_url(), **self.get_request_kwargs())

    def get_service(self, line_name):
        """Given a line name string, returns the Service matching a line name
        (case-insensitively), or a line name string
        """
        if line_name:
            line_name_lower = line_name.lower()
            if line_name_lower in self.services_by_name:
                return self.services_by_name[line_name_lower]
            if line_name_lower in self.services_by_alternative_name:
                return self.services_by_alternative_name[line_name_lower]
            alternatives = {
                'Puls': 'pulse',
                # 'FLCN': 'falcon',
                'TUBE': 'oxford tube',
                'SPRI': 'spring',
                'PRO': 'pronto',
                'SA': 'the sherwood arrow',
                'Yo-Y': 'yo-yo',
                'Port': 'portway park and ride',
                'Bris': 'brislington park and ride',
                'sp': 'sprint',
            }
            alternative = alternatives.get(line_name)
            if alternative:
                return self.get_service(alternative)
        return line_name

    def departures_from_response(self, res):
        """Given a Response object from the requests module,
        returns a list of departures
        """
        raise NotImplementedError

    def get_poorly_key(self):
        return '{}:poorly'.format(self.request_url)

    def get_poorly(self):
        return cache.get(self.get_poorly_key())

    def set_poorly(self, age):
        key = self.get_poorly_key()
        if key:
            return cache.set(key, True, age)

    def get_departures(self):
        try:
            response = self.get_response()
        except requests.exceptions.ReadTimeout:
            self.set_poorly(60)  # back off for 1 minute
            return
        except requests.exceptions.RequestException as e:
            self.set_poorly(60)  # back off for 1 minute
            logger.error(e, exc_info=True)
            return
        if response.ok:
            return self.departures_from_response(response)
        self.set_poorly(1800)  # back off for 30 minutes


class TflDepartures(Departures):
    """Departures from the Transport for London API"""
    @staticmethod
    def get_request_params():
        return settings.TFL

    def get_request_url(self):
        return f'https://api.tfl.gov.uk/StopPoint/{self.stop.pk}/arrivals'

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
            'link': f"/vehicles/tfl/{item['vehicleId']}",
        } for item in rows], key=lambda d: d['live'])


class WestMidlandsDepartures(Departures):
    @staticmethod
    def get_request_params():
        return {
            **settings.TFWM,
            'formatter': 'json'
        }

    def get_request_url(self):
        return f'http://api.tfwm.org.uk/stoppoint/{self.stop.pk}/arrivals'

    def departures_from_response(self, res):
        return sorted([{
            'time': ciso8601.parse_datetime(item['ScheduledArrival']),
            'live': ciso8601.parse_datetime(item['ExpectedArrival']),
            'service': self.get_service(item['LineName']),
            'destination': item['DestinationName'],
        } for item in res.json()['Predictions']['Prediction'] if item['ExpectedArrival']], key=lambda d: d['live'])


class EdinburghDepartures(Departures):
    def get_request_url(self):
        return 'http://tfe-opendata.com/api/v1/live_bus_times/' + self.stop.naptan_code

    def departures_from_response(self, res):
        routes = res.json()
        if routes:
            departures = []
            for route in routes:
                service = self.get_service(route['routeName'])
                for departure in route['departures']:
                    time = ciso8601.parse_datetime(departure['departureTime'])
                    departures.append({
                        'time': None if departure['isLive'] else time,
                        'live': time if departure['isLive'] else None,
                        'service': service,
                        'destination': departure['destination']
                    })
            hour = datetime.timedelta(hours=1)
            if all(
                ((departure['time'] or departure['live']) - self.now) >= hour for departure in departures
            ):
                for departure in departures:
                    if departure['time']:
                        departure['time'] -= hour
                    else:
                        departure['live'] -= hour
            return departures


class AcisHorizonDepartures(Departures):
    """Departures from a SOAP endpoint (lol)"""
    request_url = 'http://belfastapp.acishorizon.com/DataService.asmx'
    headers = {
        'content-type': 'application/soap+xml'
    }
    ns = {
        'a': 'http://www.acishorizon.com/',
        's': 'http://www.w3.org/2003/05/soap-envelope'
    }

    def get_response(self):
        data = """
            <s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
                <s:Body>
                    <GetArrivalsForStops xmlns="http://www.acishorizon.com/">
                        <stopRefs>
                            <string>{}</string>
                        </stopRefs>
                        <maxResults>10</maxResults>
                    </GetArrivalsForStops>
                </s:Body>
            </s:Envelope>
        """.format(self.stop.pk)
        return requests.post(self.request_url, headers=self.headers, data=data, timeout=2)

    def departures_from_response(self, res):
        items = ET.fromstring(res.text)
        items = items.find('s:Body/a:GetArrivalsForStopsResponse/a:GetArrivalsForStopsResult', self.ns)
        items = items.findall('a:Stops/a:VirtualStop/a:StopArrivals/a:StopRealtime', self.ns)
        return [item for item in [self.get_row(item) for item in items] if item]

    def get_row(self, item):
        row = {
            'service': self.get_service(item.find('a:JourneyPublicServiceCode', self.ns).text),
            'destination': item.find('a:Destination', self.ns).text
        }
        time = item.find('a:TimeAsDateTime', self.ns).text
        if time:
            time = parse_datetime(time)
            if item.find('a:IsPredicted', self.ns).text == 'true':
                row['live'] = time
                row['time'] = None
            else:
                row['time'] = time
            return row


class TimetableDepartures(Departures):
    def get_row(self, stop_time, midnight):
        trip = stop_time.trip
        destination = trip.destination
        if stop_time.departure is not None:
            time = midnight + stop_time.departure
        else:
            time = midnight + stop_time.arrival
        return {
            'origin_departure_time': midnight + trip.start,
            'time': time,
            'destination': destination.locality or destination.town or destination.common_name,
            'service': trip.route.service,
            'link': trip.get_absolute_url()
        }

    def get_times(self, when):
        times = get_stop_times(when, self.stop.atco_code, self.services, self.routes)
        times = times.select_related('trip__route__service', 'trip__destination__locality')
        times = times.defer('trip__route__service__geometry', 'trip__route__service__search_vector',
                            'trip__destination__locality__latlong', 'trip__destination__locality__search_vector')
        return times.order_by('departure')

    def get_departures(self):
        key = f'TimetableDepartures:{self.stop.atco_code}'
        times = cache.get(key)
        if times is not None:
            return times
        time_since_midnight = datetime.timedelta(hours=self.now.hour, minutes=self.now.minute, seconds=self.now.second,
                                                 microseconds=self.now.microsecond)
        midnight = self.now - time_since_midnight
        times = [self.get_row(stop_time, midnight) for stop_time in self.get_times(self.now)[:10]]
        i = 0
        while len(times) < 10 and i < 3:
            i += 1
            midnight += datetime.timedelta(1)
            times += [self.get_row(stop_time, midnight) for stop_time in self.get_times(midnight)[:10-len(times)]]
        if times:
            max_age = (times[0]['time'] - self.now).seconds + 60
            cache.set(key, times, max_age)
        return times

    def __init__(self, stop, services, now, routes):
        self.routes = routes
        super().__init__(stop, services, now)


def parse_datetime(string):
    return ciso8601.parse_datetime(string).astimezone(LOCAL_TIMEZONE)


class SiriSmDepartures(Departures):
    ns = {
        's': 'http://www.siri.org.uk/siri'
    }
    data_source = None

    def __init__(self, source, stop, services):
        self.source = source
        super().__init__(stop, services)

    def get_row(self, item):
        journey = item['MonitoredVehicleJourney']

        call = journey['MonitoredCall']
        aimed_time = call.get('AimedDepartureTime')
        expected_time = call.get('ExpectedDepartureTime')
        if aimed_time:
            aimed_time = parse_datetime(aimed_time)
        if expected_time:
            expected_time = parse_datetime(expected_time)

        line_name = journey.get('LineName') or journey.get('LineRef')
        destination = journey.get('DestinationName') or journey.get('DestinationDisplay')

        service = self.get_service(line_name)

        return {
            'time': aimed_time,
            'live': expected_time,
            'service': service,
            'destination': destination,
            'data': journey
        }

    def get_poorly_key(self):
        return self.source.get_poorly_key()

    def departures_from_response(self, response):
        if not response.text or 'Client.AUTHENTICATION_FAILED' in response.text:
            cache.set(self.get_poorly_key(), True, 1800)  # back off for 30 minutes
            return
        data = xmltodict.parse(response.text)
        try:
            data = data['Siri']['ServiceDelivery']['StopMonitoringDelivery']['MonitoredStopVisit']
        except (KeyError, TypeError):
            return
        if type(data) is list:
            return [self.get_row(item) for item in data]
        return [self.get_row(data)]

    def get_response(self):
        if self.source.requestor_ref:
            username = '<RequestorRef>{}</RequestorRef>'.format(self.source.requestor_ref)
        else:
            username = ''
        timestamp = '<RequestTimestamp>{}</RequestTimestamp>'.format(datetime.datetime.utcnow().isoformat())
        request_xml = """
            <Siri version="1.3" xmlns="http://www.siri.org.uk/siri">
                <ServiceRequest>
                    {}
                    {}
                    <StopMonitoringRequest version="1.3">
                        {}
                        <MonitoringRef>{}</MonitoringRef>
                    </StopMonitoringRequest>
                </ServiceRequest>
            </Siri>
        """.format(timestamp, username, timestamp, self.stop.atco_code)
        headers = {'Content-Type': 'application/xml'}
        return requests.post(self.source.url, data=request_xml, headers=headers, timeout=5)


class StagecoachDepartures(Departures):
    def get_response(self):
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
                        'stopPointLabel': self.stop.atco_code,
                        'servicesFilters': {}
                    }]
                }
            }
        }
        return requests.post('https://api.stagecoachbus.com/adc/stop-monitor',
                             headers=headers, json=json, timeout=2)

    def departures_from_response(self, response):
        stop_monitors = response.json()['stopMonitors']
        departures = []

        if 'stopMonitor' in stop_monitors:
            for monitor in stop_monitors['stopMonitor'][0]['monitoredCalls']['monitoredCall']:

                if 'expectedDepartureTime' not in monitor:
                    continue

                departures.append({
                    'time': parse_datetime(monitor['aimedDepartureTime']),
                    'live': parse_datetime(monitor['expectedDepartureTime']),
                    'service': self.get_service(monitor['lineRef']),
                    'destination': monitor['destinationDisplay'],
                })

        return departures


def services_match(a, b):
    if type(a) is Service:
        a = a.line_name
    if type(b) is Service:
        b = b.line_name
    return a.lower() == b.lower()


def can_sort(departure):
    return type(departure['time']) is datetime.datetime or type(departure.get('live')) is datetime.datetime


def get_departure_order(departure):
    if departure.get('live') and (not departure['time'] or departure['time'].date() == departure['live'].date()):
        time = departure['live']
    else:
        time = departure['time']
    if timezone.is_naive(time):
        return time
    return timezone.make_naive(time, LOCAL_TIMEZONE)


def blend(departures, live_rows, stop=None):
    added = False
    for live_row in live_rows:
        replaced = False
        for row in departures:
            if services_match(row['service'], live_row['service']) and row['time'] and live_row['time']:
                if abs(row['time'] - live_row['time']) <= datetime.timedelta(minutes=2):
                    if live_row.get('live'):
                        row['live'] = live_row['live']
                    if 'data' in live_row:
                        row['data'] = live_row['data']
                    replaced = True
                    break
        if not replaced and (live_row.get('live') or live_row['time']):
            departures.append(live_row)
            added = True
    if added and all(can_sort(departure) for departure in departures):
        departures.sort(key=get_departure_order)


def get_stop_times(when, stop, services, services_routes):
    time_since_midnight = datetime.timedelta(hours=when.hour, minutes=when.minute, seconds=when.second)
    times = StopTime.objects.filter(~Q(activity='setDown'), stop_id=stop)
    if time_since_midnight:
        times = times.filter(departure__gte=time_since_midnight)
    services = [service for service in services if not service.timetable_wrong]
    services = {}
    routes = []
    for service_routes in services_routes.values():
        routes += get_routes(service_routes, when.date())
    return times.filter(trip__route__in=routes, trip__calendar__in=get_calendars(when))


def get_departures(stop, services):
    """Given a StopPoint object and an iterable of Service objects,
    returns a tuple containing a context dictionary and a max_age integer
    """

    # Transport for London
    if any(service.service_code[:4] == 'tfl_' for service in services):
        departures = TflDepartures(stop, services)
        return ({
            'departures': departures,
            'today': timezone.localdate(),
        }, 60)

    now = timezone.localtime()

    routes = {}
    for route in Route.objects.filter(service__in=services).select_related('source'):
        if route.service_id in routes:
            routes[route.service_id].append(route)
        else:
            routes[route.service_id] = [route]

    departures = TimetableDepartures(stop, services, now, routes)
    departures = departures.get_departures()

    one_hour = datetime.timedelta(hours=1)

    if not departures or (departures[0]['time'] - now) < one_hour or (
        get_stop_times(now - one_hour, stop.atco_code, services, routes)
    ).exists():

        operators = set()
        for service in services:
            for operator in service.operators:
                if operator:
                    operators.add(operator)

        live_rows = None

        # Belfast
        if stop.atco_code[0] == '7' and ('Translink Metro' in operators or 'Translink Glider' in operators):
            live_rows = AcisHorizonDepartures(stop, services).get_departures()
            if live_rows:
                blend(departures, live_rows)
        elif departures:
            if (
                'Lothian Buses' in operators
                or 'Lothian Country Buses' in operators
                or 'East Coast Buses' in operators
                or 'Edinburgh Trams' in operators
            ):
                live_rows = EdinburghDepartures(stop, services, now).get_departures()
                if live_rows:
                    departures = live_rows
                    live_rows = None

            source = None

            if stop.admin_area_id:
                service_code_exists = Exists(
                    ServiceCode.objects.filter(service__in=services, scheme=Concat(OuterRef('name'), Value(' SIRI')))
                )
                possible_sources = SIRISource.objects.filter(service_code_exists | Q(admin_areas=stop.admin_area_id))
                for possible_source in possible_sources:
                    if not possible_source.get_poorly():
                        source = possible_source
                        break

            if source:
                live_rows = SiriSmDepartures(source, stop, services).get_departures()
            elif stop.atco_code[:3] == '430':
                live_rows = WestMidlandsDepartures(stop, services).get_departures()

            if any(operator[:11] == 'Stagecoach ' for operator in operators):
                if not (live_rows and any(
                    row.get('live') and type(row['service']) is Service and any(
                        operator.name[:11] == 'Stagecoach ' for operator in row['service'].operator.all()
                    ) for row in live_rows
                )):
                    stagecoach_rows = StagecoachDepartures(stop, services).get_departures()
                    if stagecoach_rows:
                        blend(departures, stagecoach_rows)

            if live_rows:
                blend(departures, live_rows)

                if source and source.name in {'Aberdeen', 'SPT'}:
                    # Record some information about the vehicle and journey,
                    # for enthusiasts,
                    # because the source doesn't support vehicle locations
                    for row in departures:
                        if 'data' in row and 'VehicleRef' in row['data']:
                            log_vehicle_journey.delay(
                                row['service'].pk if type(row['service']) is Service else None,
                                row['data'],
                                str(row['origin_departure_time']) if 'origin_departure_time' in row else None,
                                str(row['destination']),
                                source.name,
                                source.url,
                                row.get('link')
                            )

    max_age = 60

    return ({
        'departures': departures,
        'today': now.date(),
    },  max_age)

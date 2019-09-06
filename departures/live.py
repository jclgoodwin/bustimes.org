"""Various ways of getting live departures from some web service"""
import re
import ciso8601
import datetime
import requests
import pytz
import dateutil.parser
import logging
import xml.etree.cElementTree as ET
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone
from busstops.models import Service, ServiceCode, DataSource, SIRISource
from vehicles.models import Vehicle, VehicleJourney, JourneyCode


logger = logging.getLogger(__name__)
DESTINATION_REGEX = re.compile(r'.+\((.+)\)')
LOCAL_TIMEZONE = pytz.timezone('Europe/London')
SESSION = requests.Session()


class Departures(object):
    """Abstract class for getting departures from a source"""
    def __init__(self, stop, services, now=None):
        self.stop = stop
        self.now = now
        self.services = {}
        duplicate_line_names = set()
        for service in services:
            line_name = service.line_name.lower()
            if line_name in self.services:
                duplicate_line_names.add(line_name)
            else:
                self.services[line_name] = service
            if service.net:
                # there's sometimes an alternative abbreviated line name hidden in the service code
                parts = service.service_code.split('-')
                part = parts[1].lower()
                if part != line_name:
                    if part in self.services:
                        duplicate_line_names.add(part)
                    else:
                        self.services[part] = service
        for line_name in duplicate_line_names:
            del self.services[line_name]

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
            'timeout': 5
        }

    def get_response(self):
        return SESSION.get(self.get_request_url(), **self.get_request_kwargs())

    def get_service(self, line_name):
        """Given a line name string, returns the Service matching a line name
        (case-insensitively), or a line name string
        """
        if line_name:
            line_name_lower = line_name.lower()
            if line_name_lower in self.services:
                return self.services[line_name_lower]
            alternatives = {
                'Puls': 'pulse',
                'FLCN': 'falcon',
                'TUBE': 'oxford tube',
                'SPRI': 'spring',
                'PRO': 'pronto',
                'SA': 'the sherwood arrow',
                'Yo-Y': 'yoyo',
                'Port': 'portway park and ride',
                'Bris': 'brislington park and ride',
                'sp': 'sprint',
            }
            alternative = alternatives.get(line_name)
            if alternative and alternative in self.services:
                return self.services[alternative]
        return line_name

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
        if response and response.ok:
            return self.departures_from_response(response)

    def log_vehicle_journey(self, operator_ref, vehicle, service, journey_ref, destination, departure_time):
        if not self.data_source:
            self.data_source, _ = DataSource.objects.get_or_create({'url': self.source.url}, name=self.source.name)
        defaults = {
            'source': self.data_source
        }
        if operator_ref and vehicle.startswith(operator_ref + '-'):
            vehicle = vehicle[len(operator_ref) + 1:]
        elif operator_ref == 'FAB' and vehicle.startswith('111-'):  # Aberdeen
            vehicle = vehicle[4:]
        elif vehicle.startswith('ASES-'):  # Milton Keynes
            vehicle = vehicle[5:]
        operator = service.operator.all()[0]
        for operator in service.operator.all():
            if operator.name[:11] == 'Stagecoach ':
                return
        if not vehicle or vehicle == '-':
            return
        if vehicle.isdigit():
            defaults['code'] = vehicle
            vehicle, created = Vehicle.objects.get_or_create(defaults, operator=operator, fleet_number=vehicle)
        else:
            vehicle, created = Vehicle.objects.get_or_create(defaults, operator=operator, code=vehicle)

        if journey_ref and journey_ref.startswith('Unknown'):
            journey_ref = ''

        if not (departure_time or journey_ref):
            return

        destination = destination or ''
        if journey_ref:
            try:
                existing_journey = VehicleJourney.objects.get(vehicle=vehicle, service=service, code=journey_ref,
                                                              datetime__date=departure_time.date())
                if existing_journey.datetime != departure_time:
                    existing_journey.datetime = departure_time
                    existing_journey.save()
            except VehicleJourney.DoesNotExist:
                VehicleJourney.objects.create(vehicle=vehicle, service=service, code=journey_ref,
                                              datetime=departure_time,
                                              source=self.data_source, destination=destination)
            except VehicleJourney.MultipleObjectsReturned:
                pass
        else:
            defaults = {
                'destination': destination,
                'source': self.data_source
            }
            VehicleJourney.objects.get_or_create(defaults, vehicle=vehicle, service=service,
                                                 datetime=departure_time)


class DublinDepartures(Departures):
    def get_request_url(self):
        return 'http://data.smartdublin.ie/cgi-bin/rtpi/realtimebusinformation'

    def get_request_params(self):
        return {
            'stopid': int(self.stop.atco_code.split('B', 1)[-1])
        }

    def departures_from_response(self, response):
        return [{
            'time': dateutil.parser.parse(item['scheduleddeparturedatetime'], dayfirst=True),
            'live': dateutil.parser.parse(item['departuredatetime'], dayfirst=True),
            'destination': item['destination'],
            'service': self.get_service(item['route'])
        } for item in response.json()['results']]


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


class GoAheadDepartures(Departures):
    def get_request_url(self):
        return 'https://api.otrl-bus.io/api/stops/departures/' + self.stop.pk

    def get_request_headers(self):
        return {
            'opco': 'goNorthWest'
        }

    def get_row(self, row):
        time = row['monitoredCall']['aimedDepartureTimeUTC']
        live = row['monitoredCall']['expectedDepartureTimeUTC']
        return {
            'time': parse_datetime(time),
            'live': parse_datetime(live) if live and row['monitored'] else None,
            'service': self.get_service(row['publishedLineName']),
            'destination': row['destinationName']
        }

    def departures_from_response(self, res):
        return [self.get_row(row) for row in res.json()['data']]


class PolarBearDepartures(Departures):
    def get_request_url(self):
        return 'https://{}.arcticapi.com/network/stops/{}/visits'.format(self.prefix, self.stop.pk)

    def departures_from_response(self, res):
        res = res.json()
        if '_embedded' in res:
            return [{
                'time': ciso8601.parse_datetime(item['aimedDepartureTime']),
                'live': ciso8601.parse_datetime(item['expectedDepartureTime']),
                'service': self.get_service(item['_links']['transmodel:line']['name']),
                'destination': item['destinationName'],
            } for item in res['_embedded']['timetable:visit'] if 'expectedDepartureTime' in item]

    def __init__(self, prefix, stop, services):
        self.prefix = prefix
        super().__init__(stop, services)


class AcisHorizonDepartures(Departures):
    """Departures from a SOAP endpoint (lol)"""
    url = 'http://belfastapp.acishorizon.com/DataService.asmx'
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
        return SESSION.post(self.url, headers=self.headers, data=data, timeout=2)

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
            time = timezone.make_aware(ciso8601.parse_datetime(item['date'] + ' ' + time))
            if live_time:
                live_time = timezone.make_aware(ciso8601.parse_datetime(item['date'] + ' ' + live_time))
            if (item['source'].startswith('Traveline timetable') and time.date() > self.today):
                return
        else:
            time = timezone.make_aware(datetime.datetime.combine(
                self.today, dateutil.parser.parse(time).time()
            ))
            if live_time:
                live_time = timezone.make_aware(datetime.datetime.combine(
                    self.today, dateutil.parser.parse(live_time).time()
                ))
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
            'group': 'no',
            'nextbuses': 'no'
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


class WestDepartures(Departures):
    def get_request_url(self):
        return 'https://journeyplanner.travelwest.info/api/idox/'

    def get_request_params(self):
        return {
            'stopID': self.stop.atco_code,
            'maxItems': 10,
            'lookAheadMinutes': 180
        }

    def get_row(self, item):
        time = item['scheduledCall']['scheduledDepartureTime']
        if not time:
            return
        live = item.get('expectedDepartureTime')
        if live:
            live = ciso8601.parse_datetime(live)
        return {
            'time': ciso8601.parse_datetime(time),
            'live': live,
            'service': self.get_service(item['routeInfo']['lineName']),
            'destination': item['tripInfo']['headsign'],
            'vehicle': item['vehicleRTI']['vehicleID'],
            'operator': item['agencyCode'],
        }

    def departures_from_response(self, res):
        rows = (self.get_row(item) for item in res.json()['data']['rtiReports'][0]['upcomingCalls'])
        return [row for row in rows if row]


class NorfokDepartures(Departures):
    def get_request_url(self):
        return 'https://ldb.norfolkbus.info/public/displays/ncc1/transitdb/querylegacytable/timetable'

    def get_request_params(self):
        return {
            'stopId': 'NaPTAN_' + self.stop.atco_code,
            'stopIdType': 'native'
        }

    def departures_from_response(self, res):
        departures = []
        res = res.json()['r']
        for i in range(0, int(len(res[1]) / 11)):
            item = (res[1][i * 11: (i + 1) * 11])
            time = timezone.make_aware(datetime.datetime.fromtimestamp(int(item[3])))
            live = item[4]
            if live:
                live = timezone.make_aware(datetime.datetime.fromtimestamp(int(live)))
            if not live or time < self.now and live < self.now:
                continue
            departures.append({
                'time': time,
                'live': live,
                'service': self.get_service(item[2]),
                'destination': item[6],
            })
        return departures


class TimetableDepartures(Departures):
    def get_row(self, suu):
        destination = suu.journey.destination
        service = self.get_service(suu.journey.service.line_name)
        if type(service) is not Service:
            service = suu.journey.service
        return {
            'time': timezone.localtime(suu.datetime),
            'destination': destination.locality or destination.town or destination,
            'service': service,
            'origin_departure_time': suu.journey.datetime
        }

    def get_departures(self):
        queryset = self.stop.stopusageusage_set.filter(datetime__gte=self.now,
                                                       journey__service__timetable_wrong=False)
        queryset = queryset.select_related('journey__destination__locality', 'journey__service')
        queryset = queryset.defer('journey__destination__latlong', 'journey__destination__locality__latlong',
                                  'journey__service__geometry')[:10]
        return [self.get_row(suu) for suu in queryset]


def parse_datetime(string):
    return ciso8601.parse_datetime(string).astimezone(LOCAL_TIMEZONE)


class SiriSmDepartures(Departures):
    ns = {
        's': 'http://www.siri.org.uk/siri'
    }
    data_source = None

    def __init__(self, source, stop, services):
        self.source = source
        self.line_refs = set()
        super().__init__(stop, services)

    def log_vehicle_journey(self, element, operator_ref, vehicle, service, journey_ref, destination):
        if operator_ref == 'UNIB':
            return
        origin_aimed_departure_time = element.find('s:OriginAimedDepartureTime', self.ns)
        if origin_aimed_departure_time is None:
            return
        origin_aimed_departure_time = parse_datetime(origin_aimed_departure_time.text)
        super().log_vehicle_journey(operator_ref, vehicle, service, journey_ref, destination,
                                    origin_aimed_departure_time)

    def get_row(self, element):
        aimed_time = element.find('s:MonitoredCall/s:AimedDepartureTime', self.ns)
        expected_time = element.find('s:MonitoredCall/s:ExpectedDepartureTime', self.ns)
        line_name = element.find('s:PublishedLineName', self.ns)
        line_ref = element.find('s:LineRef', self.ns)
        destination = element.find('s:DestinationName', self.ns)
        if aimed_time is not None:
            aimed_time = parse_datetime(aimed_time.text)
        if expected_time is not None:
            expected_time = parse_datetime(expected_time.text)
        if line_name is None:
            line_name = line_ref
        if line_name is not None:
            line_name = line_name.text
        if destination is None:
            destination = element.find('s:DestinationDisplay', self.ns)
        if destination is not None:
            destination = destination.text
        operator = element.find('s:OperatorRef', self.ns)
        if operator is not None:
            operator = operator.text
        vehicle = element.find('s:VehicleRef', self.ns)
        if vehicle is not None:
            vehicle = vehicle.text
        service = self.get_service(line_name)

        if type(service) is Service:
            journey_ref = element.find('s:FramedVehicleJourneyRef/s:DatedVehicleJourneyRef', self.ns)
            if journey_ref is not None:
                journey_ref = journey_ref.text

            scheme = self.source.name
            url = self.source.url

            # Record some information about the vehicle and journey,
            # for enthusiasts,
            # because the source doesn't support vehicle locations
            if vehicle:
                if not ('sslink' in url or 'jmwrti' in url or scheme in {'Reading', 'Surrey'}):
                    try:
                        self.log_vehicle_journey(element, operator, vehicle, service, journey_ref, destination)
                    except (Vehicle.MultipleObjectsReturned, VehicleJourney.MultipleObjectsReturned):
                        pass

            # Create a "service code",
            # because the source supports vehicle locations.
            # For Norfolk, the code is useful for deciphering out what route a vehicle is on.
            # For other sources, it just denotes that some live tracking is available.
            if line_ref is not None:
                if expected_time and ('icarus' in url or 'sslink' in url):
                    scheme += ' SIRI'
                    line_ref = line_ref.text
                    if line_ref and line_ref not in self.line_refs and operator != 'TD':
                        ServiceCode.objects.update_or_create({'code': line_ref}, service=service, scheme=scheme)
                        self.line_refs.add(line_ref)

            # Create a "journey code", which can be used to work out the destination of a vehicle.
            if 'jmwrti' in url and destination and journey_ref:
                try:
                    JourneyCode.objects.update_or_create({
                        'destination': destination
                    }, service=service, code=journey_ref, siri_source=self.source)
                except JourneyCode.MultipleObjectsReturned:
                    pass

        return {
            'time': aimed_time,
            'live': expected_time,
            'service': service,
            'destination': destination,
        }

    def get_departures(self):
        try:
            response = self.get_response()
        except requests.exceptions.RequestException:
            cache.set(self.source.get_poorly_key(), True, 60)  # back off for 1 minute
            return
        if response.ok:
            return self.departures_from_response(response)
        cache.set(self.source.get_poorly_key(), True, 1800)  # back off for 30 minutes

    def departures_from_response(self, response):
        if not response.text or 'Client.AUTHENTICATION_FAILED' in response.text:
            cache.set(self.source.get_poorly_key(), True, 1800)  # back off for 30 minutes
            return
        try:
            tree = ET.fromstring(response.text).find('s:ServiceDelivery', self.ns)
        except ET.ParseError as e:
            logger.error(e, exc_info=True)
            return
        if tree is None:
            return
        departures = tree.findall('s:StopMonitoringDelivery/s:MonitoredStopVisit/s:MonitoredVehicleJourney', self.ns)
        return [self.get_row(element) for element in departures]

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
        return SESSION.post(self.source.url, data=request_xml, headers=headers, timeout=5)


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
                if departures and aimed >= (departures[0]['time'] or departures[0]['live']):
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
                        if not departure.get('live'):
                            if type(departure['service']) is Service and line == departure['service'].line_name:
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
            departures.sort(key=get_departure_order)
    return departures


def services_match(a, b):
    if type(a) == Service:
        a = a.line_name
    if type(b) == Service:
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


def log_journeys(departures, source):
    data_source = None
    for item in departures:
        if item.get('origin_departure_time') and item.get('vehicle'):
            if not data_source:
                data_source, _ = DataSource.objects.get_or_create({'url': source.url}, name=source.name)
            defaults = {
                'source': data_source
            }
            vehicle = item['vehicle']
            operator = item['operator']
            service = item['service']
            if operator and vehicle.startswith(operator + '-'):
                vehicle = vehicle[len(operator) + 1:]
            operator = service.operator.all()[0]
            operator_id = operator.id
            if vehicle.isdigit():
                defaults['fleet_number'] = vehicle
            elif operator_id == 'FBRI':
                operator_id = 'ABUS'
            if operator.name.startswith('Stagecoach '):
                continue
            else:
                vehicle, created = Vehicle.objects.get_or_create(defaults, code=vehicle, operator_id=operator_id)
            existing_journey = vehicle.vehiclejourney_set.filter(datetime=item['origin_departure_time'])
            if created or not existing_journey.exists():
                VehicleJourney.objects.create(source=data_source, vehicle=vehicle, service=service,
                                              datetime=item['origin_departure_time'],
                                              destination=item['destination'])


def blend(departures, live_rows, stop=None):
    added = False
    for live_row in live_rows:
        replaced = False
        for row in departures:
            if (
                services_match(row['service'], live_row['service']) and
                row['time'] and row['time'] == live_row['time']
            ):
                if live_row.get('live'):
                    row['live'] = live_row['live']
                if 'vehicle' in live_row:
                    row['vehicle'] = live_row['vehicle']
                    row['operator'] = live_row['operator']
                replaced = True
                break
        if not replaced and (live_row.get('live') or live_row['time']):
            departures.append(live_row)
            added = True
    if added and all(can_sort(departure) for departure in departures):
        departures.sort(key=get_departure_order)


def get_departures(stop, services):
    """Given a StopPoint object and an iterable of Service objects,
    returns a tuple containing a context dictionary and a max_age integer
    """

    # 🚂
    if stop.atco_code[:3] == '910':
        departures = UKTrainDepartures(stop, ())
        return ({
            'departures': departures,
            'today': datetime.date.today(),
        }, 30)

    # Transport for London
    if any(service.net == 'tfl' for service in services):
        departures = TflDepartures(stop, services)
        return ({
            'departures': departures,
            'today': datetime.date.today(),
        }, 60)

    # Dublin
    if stop.atco_code[0] == '8' and 'DB' in stop.atco_code:
        return ({
            'departures': DublinDepartures(stop, services).get_departures(),
            'today': datetime.date.today(),
        }, 60)

    # Jersey
    if stop.atco_code[:3] == 'je-':
        return ({
            'departures': JerseyDepartures(stop, services).get_departures(),
            'today': datetime.date.today(),
        }, 60)

    now = timezone.localtime()

    departures = TimetableDepartures(stop, services, now)
    services_dict = departures.services
    departures = departures.get_departures()

    one_hour = datetime.timedelta(hours=1)
    one_hour_ago = stop.stopusageusage_set.filter(datetime__lte=now - one_hour, journey__service__current=True)

    if not departures or (departures[0]['time'] - now) < one_hour or one_hour_ago.exists():

        operators = set()
        for service in services:
            for operator in service.operator.all():
                operators.add(operator)

        live_rows = None

        # Belfast
        if stop.atco_code[0] == '7' and any(operator.id == 'MET' or operator.id == 'GDR' for operator in operators):
            live_rows = AcisHorizonDepartures(stop, services).get_departures()
            if live_rows:
                blend(departures, live_rows)
        elif departures:
            if any(operator.id in {'LOTH', 'LCBU', 'NELB', 'EDTR'} for operator in operators):
                live_rows = EdinburghDepartures(stop, services, now).get_departures()
            elif any(operator.id == 'GONW' for operator in operators):
                live_rows = GoAheadDepartures(stop, services).get_departures()
            if live_rows:
                blend(departures, live_rows)
                live_rows = None

            source = None
            schemes = ServiceCode.objects.filter(service__current=True, service__stops=stop)
            schemes = schemes.values_list('scheme', flat=True).distinct()
            if stop.admin_area:
                schemes = [scheme.replace(' SIRI', '') for scheme in schemes]
                possible_sources = SIRISource.objects.filter(Q(name__in=schemes) | Q(admin_areas=stop.admin_area))
                for possible_source in possible_sources:
                    if not possible_source.get_poorly():
                        source = possible_source
                        break

            if source:
                if source.name == 'Bristol':
                    live_rows = WestDepartures(stop, services).get_departures()
                else:
                    live_rows = SiriSmDepartures(source, stop, services).get_departures()
            elif any(operator.id in {'FSCE', 'FCYM'} for operator in operators):
                live_rows = TransportApiDepartures(stop, services, now.date()).get_departures()
            elif stop.atco_code[:3] == '430':
                live_rows = WestMidlandsDepartures(stop, services).get_departures()
            elif any(operator.id in {'YCST', 'HRGT', 'KDTR'} for operator in operators):
                live_rows = PolarBearDepartures('transdevblazefield', stop, services).get_departures()
            elif stop.atco_code[:3] == '290':
                live_rows = NorfokDepartures(stop, services, now).get_departures()

            if any(operator.name[:11] == 'Stagecoach ' for operator in operators):
                if not (live_rows and any(
                    row.get('live') and type(row['service']) is Service and any(
                        operator.name[:11] == 'Stagecoach ' for operator in row['service'].operator.all()
                    ) for row in live_rows
                )):
                    departures = add_stagecoach_departures(stop, services_dict, departures)

            if live_rows:
                blend(departures, live_rows)

                if source and source.name == 'Bristol':
                    log_journeys(departures, source)

    max_age = 60

    return ({
        'departures': departures,
        'today': now.date(),
    },  max_age)

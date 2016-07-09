import re
from datetime import datetime, date

import requests
import pytz
from bs4 import BeautifulSoup
from django.conf import settings
from django.utils.text import slugify


DESTINATION_REGEX = re.compile(r'.+\((.+)\)')


class Departures(object):
    def __init__(self, stop, services):
        self.stop = stop
        self.services = {
            service.line_name.split('|', 1)[0].lower(): service
            for service in services
        }

    def get_response_args(self):
        raise NotImplementedError

    def get_response(self):
        return requests.get(*self.get_response_args())

    def get_service(self, line_name):
        """Returns the Service matching a line name (case-insensitively), or a line name string"""
        return self.services.get(line_name.lower(), line_name)

    def departures_from_response(self, res):
        raise NotImplementedError

    def get_departures(self):
        return self.departures_from_response(self.get_response())


class TflDepartures(Departures):
    def get_response_args(self):
        return ('http://api.tfl.gov.uk/StopPoint/%s/arrivals' % self.stop.pk,)

    def departures_from_response(self, res):
        timezone = pytz.timezone('Europe/London')
        return ({
            'time': timezone.fromutc(
                datetime.strptime(item.get('expectedArrival'), '%Y-%m-%dT%H:%M:%SZ')
            ),
            'service': self.get_service(item.get('lineName')),
            'destination': item.get('destinationName'),
        } for item in res.json()) if res.status_code == 200 else ()


class AcisDepartures(Departures):
    def __init__(self, prefix, stop, services):
        self.prefix = prefix
        super(AcisDepartures, self).__init__(stop, services)


class AcisLiveDepartures(AcisDepartures):
    def get_response_args(self):
        return ('http://%s.acislive.com/pip/stop_simulator_table.asp' % self.prefix, {
            'naptan': self.stop.naptan_code
        })

    def departures_from_response(self, res):
        if res.status_code != 200:
            return ()
        soup = BeautifulSoup(res.text, 'html.parser')
        cells = [cell.text.strip() for cell in soup.find_all('td')]
        rows = (cells[i * 4 - 4:i * 4] for i in range(1, (len(cells)/4) + 1))
        return ({
            'time': row[2],
            'service': self.get_service(row[0]),
            'destination': row[1]
        } for row in rows)


class AcisConnectDepartures(AcisDepartures):
    @staticmethod
    def get_time(cell):
        text = cell.text
        if text == '1 Mins':
            return '1 min'
        return text.replace('Mins', 'mins')

    def get_response_args(self):
        return ('http://%s.acisconnect.com/Text/WebDisplay.aspx' % self.prefix, {
            'stopRef': self.stop.naptan_code if self.prefix == 'yorkshire' else self.stop.pk
        })

    def departures_from_response(self, res):
        if res.status_code != 200:
            return ()
        soup = BeautifulSoup(res.text, 'html.parser')
        table = soup.find(id='GridViewRTI')
        if table is None:
            return ()
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
    def get_row(self, item):
        time = item['best_departure_estimate']
        if time is None:
            return
        if 'date' in item:
            departure_time = datetime.strptime(item['date'] + ' ' + time, '%Y-%m-%d %H:%M')
        else:
            departure_time = datetime.strptime(time, '%H:%M').time()
            departure_time = datetime.combine(date.today(), departure_time)
        destination = item.get('direction')
        destination_matches = DESTINATION_REGEX.match(destination)
        if destination_matches is not None:
            destination = destination_matches.groups()[0]
        elif item['source'] == 'VIX' and ',' in destination:
            destination = destination.split(',', 1)[0]
        return {
            'time': departure_time,
            'service': self.get_service(item.get('line').split('--', 1)[0].split('|', 1)[0]),
            'destination': destination,
        }

    def get_response_args(self):
        url = 'http://transportapi.com/v3/uk/bus/stop/%s/live.json' % self.stop.atco_code
        return (url, {
            'app_id': settings.TRANSPORTAPI_APP_ID,
            'app_key': settings.TRANSPORTAPI_APP_KEY,
            'nextbuses': 'no',
            'group': 'no',
        })

    def departures_from_response(self, res):
        departures = res.json().get('departures')
        if departures and 'all' in departures:
            return filter(None, (self.get_row(item) for item in departures.get('all')))
        return ()


def get_max_age(departures, now):
    """
    Given a list of departures and the current datetime, returns a max_age in seconds
    (for use in a cache-control header)
    """
    if len(departures) > 0:
        expiry = departures[0]['time']
        if now < expiry:
            return (expiry - now).seconds + 60
        return 60
    return 3600

def get_departures(stop, services):
    """
    Given a StopPoint object and an iterable of Service objects,
    returns a tuple containing a context dictionary and a max_age integer
    """
    live_sources = stop.live_sources.values_list('name', flat=True)

    if 'TfL' in live_sources:
        return ({
            'departures': TflDepartures(stop, services),
            'today': date.today(),
            'source': {
                'url': 'https://tfl.gov.uk/bus/stop/%s/%s' % (stop.atco_code, slugify(stop.common_name)),
                'name': 'Transport for London'
            }
        }, 60)

    if 'Y' in live_sources:
        return ({
            'departures': AcisConnectDepartures('yorkshire', stop, services),
            'source': {
                'url': 'http://yorkshire.acisconnect.com/Text/WebDisplay.aspx?stopRef=%s' % stop.naptan_code,
                'name': 'Your Next Bus'
            }
        }, 60)

    if 'Kent' in live_sources:
        return ({
            'departures': AcisLiveDepartures('kent', stop, services),
            'source': {
                'url': 'http://%s.acislive.com/pip/stop_simulator.asp?NaPTAN=%s' % ('kent', stop.naptan_code),
                'name': 'ACIS Live'
            }
        }, 60)

    for live_source_name, prefix in (
            ('ayr', 'ayrshire'), ('west', 'travelwest'), ('buck', 'buckinghamshire'),
            ('camb', 'cambridgeshire'), ('aber', 'aberdeen'), ('card', 'cardiff'),
            ('swin', 'swindon'), ('metr', 'metrobus')
    ):
        if live_source_name in live_sources:
            return ({
                'departures': AcisConnectDepartures(prefix, stop, services),
                'source': {
                    'url': 'http://%s.acisconnect.com/Text/WebDisplay.aspx?stopRef=%s' % (prefix, stop.pk),
                    'name': 'vixConnect'
                }
            }, 60)

    try:
        departures = TransportApiDepartures(stop, services).get_departures()
    except requests.exceptions.ConnectionError:
        departures = ()
    return ({
        'departures': departures,
        'today': date.today(),
        'source': None,
    }, get_max_age(departures, datetime.now()))

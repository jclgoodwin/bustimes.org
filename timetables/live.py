import requests
import pytz
import re
from bs4 import BeautifulSoup
from datetime import datetime, date
from django.conf import settings
from django.utils.text import slugify


DESTINATION_REGEX = re.compile(r'.+\((.+)\)')


def get_tfl_departures(stop, services):
    timezone = pytz.timezone('Europe/London')
    req = requests.get('http://api.tfl.gov.uk/StopPoint/%s/arrivals' % stop.pk)
    return ({
        'time': timezone.fromutc(datetime.strptime(item.get('expectedArrival'), '%Y-%m-%dT%H:%M:%SZ')),
        'service': services.get(item.get('lineName')) or item.get('lineName'),
        'destination': item.get('destinationName'),
    } for item in req.json()) if req.status_code == 200 else ()


def get_molly_departures(stop, services):
    req = requests.get('http://tsy.acislive.com/pip/stop_simulator_table.asp', {
        'naptan': stop.naptan_code
    })
    if req.status_code != 200:
        return ()
    soup = BeautifulSoup(req.text, 'html.parser')
    cells = [cell.text.strip() for cell in soup.find_all('td')]
    rows = (cells[i * 4 - 4:i * 4] for i in range(1, (len(cells)/4) + 1))
    return ({
        'time': row[2],
        'service': services.get(row[0]) or row[0],
        'destination': row[1]
    } for row in rows)


def transportapi_row(item, services):
    if item['best_departure_estimate'] is None:
        return
    if 'date' in item:
        departure_time = datetime.strptime(item['date'] + ' ' + item['best_departure_estimate'], '%Y-%m-%d %H:%M')
    else:
        departure_time = datetime.strptime(item['best_departure_estimate'], '%H:%M')
    destination = item.get('direction')
    destination_matches = DESTINATION_REGEX.match(destination)
    if destination_matches is not None:
        destination = destination_matches.groups()[0]
    return {
        'time': departure_time,
        'service': services.get(item.get('line').split('--')[0]) or item.get('line'),
        'destination': destination,
    }


def get_transportapi_departures(stop, services):
    req = requests.get('http://transportapi.com/v3/uk/bus/stop/%s/live.json' % stop.atco_code, {
       'app_id': settings.TRANSPORTAPI_APP_ID,
       'app_key': settings.TRANSPORTAPI_APP_KEY,
       'nextbuses': 'no',
       'group': 'no',
    })
    departures = req.json().get('departures')
    if departures and 'all' in departures:
        return filter(None, (transportapi_row(item, services) for item in departures.get('all')))
    return ()


def get_departures(stop, services):
    today = date.today()
    now = datetime.now()
    source = None
    live_sources = stop.live_sources.values_list('name', flat=True)
    if 'Y' in live_sources: # Yorkshire
        departures = get_molly_departures(stop, services)
        source = {
            'url': 'http://wymetro.acislive.com/pip/stop_simulator.asp?NaPTAN=%s' % stop.naptan_code,
            'name': 'ACIS Live'
        }
        max_age = 60
    elif 'TfL' in live_sources:
        departures = get_tfl_departures(stop, services)
        source = {
            'url': 'https://tfl.gov.uk/bus/stop/%s/%s' % (stop.atco_code, slugify(stop.common_name)),
            'name': 'Transport for London'
        }
        max_age = 60
    else:
        departures = get_transportapi_departures(stop, services)
        if len(departures) > 0:
            expiry = departures[0]['time']
            if expiry.year == 1900:
                expiry = expiry.combine(today, expiry.time())
            if now < expiry:
                max_age = (expiry - now).seconds + 60
            else:
                max_age = 60
        else:
            max_age = 3600
    return ({
        'departures': departures,
        'today': today,
        'source': source,
    }, max_age)

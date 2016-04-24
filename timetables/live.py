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


def get_acislive_departures(prefix, stop, services):
    req = requests.get('http://%s.acislive.com/pip/stop_simulator_table.asp' % prefix, {
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


def get_acisconnect_departures(prefix, stop, services):
    req = requests.get('http://%s.acisconnect.com/Text/WebDisplay.aspx' % prefix, {
        'stopRef': stop.pk
    })
    if req.status_code != 200:
        return ()
    soup = BeautifulSoup(req.text, 'html.parser')
    rows = (row.findAll('td') for row in soup.find(id='GridViewRTI').findAll('tr')[1:])
    return ({
        'time': row[4].text.replace('1 Mins', '1 min').replace('Mins', 'mins'),
        'service': services.get(row[0].text) or row[0].text,
        'destination': row[2].text
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
        'service': services.get(item.get('line').split('--')[0].split('|')[0]) or item.get('line'),
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
    live_sources = stop.live_sources.values_list('name', flat=True)

    if 'TfL' in live_sources:
        return ({
            'departures': get_tfl_departures(stop, services),
            'today': today,
            'source': {
                'url': 'https://tfl.gov.uk/bus/stop/%s/%s' % (stop.atco_code, slugify(stop.common_name)),
                'name': 'Transport for London'
            }
        }, 60)

    for live_source_name, prefix in (('Y', 'wymetro'), ('Kent', 'kent')):
        if live_source_name in live_sources:
            return ({
                'departures': get_acislive_departures(prefix, stop, services),
                'today': today,
                'source': {
                    'url': 'http://%s.acislive.com/pip/stop_simulator.asp?NaPTAN=%s' % (prefix, stop.naptan_code),
                    'name': 'ACIS Live'
                }
            }, 60)

    for live_source_name, prefix in (('ayr', 'ayrshire'), ('west', 'travelwest'), ('buck', 'buckinghamshire'), ('camb', 'cambridgeshire')):
        if live_source_name in live_sources:
            return ({
                'departures': get_acisconnect_departures(prefix, stop, services),
                'source': {
                    'url': 'http://%s.acisconnect.com/Text/WebDisplay.aspx?stopRef=%s' % (prefix, stop.pk),
                    'name': 'vixConnect'
                }
            }, 60)

    departures = get_transportapi_departures(stop, services)
    if len(departures) > 0:
        now = datetime.now()
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
        'source': None,
    }, max_age)

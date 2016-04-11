import requests
import pytz
import re
from datetime import datetime, date
from django.conf import settings

DESTINATION_REGEX = re.compile(r'.+\((.+)\)')


def get_tfl_departures(stop, services):
    timezone = pytz.timezone('Europe/London')
    req = requests.get('http://api.tfl.gov.uk/StopPoint/%s/arrivals' % stop.pk)
    return ({
        'time': timezone.fromutc(datetime.strptime(item.get('expectedArrival'), '%Y-%m-%dT%H:%M:%SZ')),
        'service': services.get(item.get('lineName')) or item.get('lineName'),
        'destination': item.get('destinationName'),
    } for item in req.json()) if req.status_code == 200 else ()


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
    if stop.tfl:
        departures = get_tfl_departures(stop, services)
        max_age = 120
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
    }, max_age)

import os
import requests
import datetime
from pytz.exceptions import AmbiguousTimeError
from django.utils.timezone import utc, make_aware
from django.utils.http import http_date, parse_http_date


def write_file(path, response):
    with open(path, 'wb') as open_file:
        for chunk in response.iter_content(chunk_size=102400):
            open_file.write(chunk)


def download(path, url):
    response = requests.get(url, stream=True)
    write_file(path, response)


def download_if_changed(path, url, params=None):
    headers = {
        "User-Agent": "bustimes.org"
    }
    modified = True
    if os.path.exists(path):
        headers['if-modified-since'] = http_date(os.path.getmtime(path))
        response = requests.head(url, params=params, headers=headers, timeout=10)
        if response.status_code == 304:
            modified = False

    if modified:
        response = requests.get(url, params=params, headers=headers, stream=True, timeout=10)

        if response.status_code == 304:
            modified = False
        elif not response.ok:
            modified = False
            print(response, url)
        else:
            write_file(path, response)

    last_modified = None
    if 'x-amz-meta-cb-modifiedtime' in response.headers:
        last_modified = response.headers['x-amz-meta-cb-modifiedtime']
    elif 'last-modified' in response.headers:
        last_modified = response.headers['last-modified']
    if last_modified:
        last_modified = datetime.datetime.fromtimestamp(parse_http_date(last_modified), utc)

    return modified, last_modified


def format_timedelta(duration):
    if duration is not None:
        duration = duration.total_seconds()
        hours = int(duration / 3600)
        while hours >= 24:
            hours -= 24
        minutes = int(duration % 3600 / 60)
        duration = f'{hours:0>2}:{minutes:0>2}'
        return duration


def time_datetime(time, date):
    seconds = time.total_seconds()
    while seconds >= 86400:
        date += datetime.timedelta(1)
        seconds -= 86400
    time = datetime.time(int(seconds / 3600), int(seconds % 3600 / 60), int(seconds % 60))
    combined = datetime.datetime.combine(date, time)
    try:
        return make_aware(combined)
    except AmbiguousTimeError:
        return make_aware(combined, is_dst=True)

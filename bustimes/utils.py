import os
import requests
from datetime import datetime
from django.utils.timezone import utc
from django.utils.http import http_date, parse_http_date


def write_file(path, response):
    with open(path, 'wb') as zip_file:
        for chunk in response.iter_content(chunk_size=102400):
            zip_file.write(chunk)


def download(path, url):
    response = requests.get(url, stream=True)
    write_file(path, response)


def download_if_changed(path, url):
    headers = {}
    modified = True
    if os.path.exists(path):
        headers['if-modified-since'] = http_date(os.path.getmtime(path))
        response = requests.head(url, headers=headers, timeout=10)
        if response.status_code == 304:
            modified = False

    if modified:
        response = requests.get(url, headers=headers, stream=True, timeout=10)

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
        last_modified = datetime.fromtimestamp(parse_http_date(last_modified), utc)

    return modified, last_modified

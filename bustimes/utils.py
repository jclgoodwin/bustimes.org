import os
import time
import requests
from email.utils import parsedate_to_datetime
from .management.commands.import_gtfs import write_file


def download(path, url):
    response = requests.get(url, stream=True)
    write_file(path, response)


def download_if_changed(path, url):
    headers = {}
    modified = True
    if os.path.exists(path):
        last_modified = time.localtime(os.path.getmtime(path))
        headers['if-modified-since'] = time.asctime(last_modified)

        response = requests.head(url, headers=headers)
        if response.status_code == 304:
            modified = False

    if modified:
        response = requests.get(url, headers=headers, stream=True)

        if response.status_code == 304 or not response.ok:
            modified = False
        else:
            write_file(path, response)

    last_modified = None
    if 'x-amz-meta-cb-modifiedtime' in response.headers:
        last_modified = response.headers['x-amz-meta-cb-modifiedtime']
    elif 'last-modified' in response.headers:
        last_modified = response.headers['last-modified']
    if last_modified:
        last_modified = parsedate_to_datetime(last_modified)

    return modified, last_modified

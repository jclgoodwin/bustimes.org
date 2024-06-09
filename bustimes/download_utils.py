import logging
import os
from datetime import datetime, timezone
from http import HTTPStatus

import requests
from django.utils.http import http_date, parse_http_date

session = requests.Session()


def write_file(path, response):
    with open(path, "wb") as open_file:
        for chunk in response.iter_content(chunk_size=102400):
            open_file.write(chunk)


def download(path, url):
    response = session.get(url, stream=True, timeout=60)
    assert response.ok
    write_file(path, response)


def download_if_changed(path, url, params=None):
    logger = logging.getLogger(__name__)

    headers = {"User-Agent": "bustimes.org"}
    modified = True
    if path.exists():
        headers["if-modified-since"] = http_date(os.path.getmtime(path))
        response = session.head(url, params=params, headers=headers, timeout=10)
        if response.status_code == HTTPStatus.NOT_MODIFIED:
            modified = False

    if modified:
        response = session.get(
            url, params=params, headers=headers, stream=True, timeout=10
        )

        if response.status_code == HTTPStatus.NOT_MODIFIED:
            modified = False
        elif not response.ok:
            modified = False
            logger.error(f"{response} {url}")
        else:
            write_file(path, response)

    last_modified = response.headers.get("last-modified") or response.headers.get(
        "x-amz-meta-cb-modifiedtime"
    )
    if last_modified:
        last_modified = datetime.fromtimestamp(
            parse_http_date(last_modified), timezone.utc
        )

    return modified, last_modified

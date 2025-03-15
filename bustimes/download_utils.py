import logging
from datetime import datetime, timezone
from http import HTTPStatus

import requests
from django.utils.http import http_date, parse_http_date


def write_file(path, response):
    with open(path, "wb") as open_file:
        for chunk in response.iter_content(chunk_size=102400):
            open_file.write(chunk)


def download(path, url, session=None):
    response = (session or requests).get(url, stream=True, timeout=61)
    assert response.ok
    write_file(path, response)


def download_if_modified(path, source, session=None):
    headers = {"User-Agent": "bustimes.org"}
    if source.last_modified:
        headers["if-modified-since"] = http_date(source.last_modified.timestamp())
    if source.etag:
        headers["if-none-match"] = source.etag

    response = (session or requests).get(
        source.url, headers=headers, stream=True, timeout=61
    )

    modified = response.status_code != HTTPStatus.NOT_MODIFIED

    if last_modified := response.headers.get("last-modified"):
        last_modified = datetime.fromtimestamp(
            parse_http_date(last_modified), timezone.utc
        )

    if not response.ok:
        logger = logging.getLogger(__name__)
        logger.error(f"{response} {response.url}")
    elif modified:
        write_file(path, response)

        source.last_modified = last_modified
        source.etag = response.headers.get("etag", "")
        source.save(update_fields=["last_modified", "etag"])

    return modified, last_modified

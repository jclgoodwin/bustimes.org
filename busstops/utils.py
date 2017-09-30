# coding=utf-8
import base64
import hashlib
import hmac
import os
import zipfile
try:
    from urllib.parse import urlparse, urlencode
except ImportError:
    from urlparse import urlparse
    from urllib import urlencode
from datetime import date
from django.conf import settings
from django.core.cache import cache
from timetables import txc, northern_ireland, gtfs


def format_gbp(string):
    amount = float(string)
    if amount < 1:
        return '{}p'.format(int(amount * 100))
    return '£{:.2f}'.format(amount)


def viglink(url, ref=''):
    return 'http://redirect.viglink.com/?' + urlencode(
        (
            ('key', settings.VIGLINK_KEY),
            ('u', url)
        )
    )


def sign_url(input_url=None, secret=None):
    """Given a request URL and a URL signing secret, return the signed request URL

    https://github.com/googlemaps/url-signing/blob/gh-pages/urlsigner.py
    """

    if not input_url or not secret:
        raise Exception("Both input_url and secret are required")

    url = urlparse(input_url)

    # We only need to sign the path+query part of the string
    url_to_sign = url.path + '?' + url.query

    # Decode the private key into its binary format
    # We need to decode the URL-encoded private key
    decoded_key = base64.urlsafe_b64decode(secret)

    # Create a signature using the private key and the URL-encoded
    # string using HMAC SHA1. This signature will be binary.
    signature = hmac.new(decoded_key, url_to_sign.encode('utf-8'), hashlib.sha1)

    # Encode the binary signature into base64 for use within a URL
    encoded_signature = base64.urlsafe_b64encode(signature.digest())

    original_url = url.scheme + '://' + url.netloc + url.path + '?' + url.query

    # Return signed URL
    return original_url + '&signature=' + encoded_signature.decode('utf-8')


def get_filenames(service, path=None, archive=None):
    suffix = '' if archive is None else '.xml'

    if service.region_id == 'NE':
        return ['%s%s' % (service.pk, suffix)]
    if service.region_id in ('S', 'Y'):
        return ['SVR%s%s' % (service.pk, suffix)]

    try:
        if archive is None:
            namelist = os.listdir(path)
        else:
            namelist = archive.namelist()
    except (IOError, OSError):
        return []

    if service.net:
        return [name for name in namelist if name.startswith('%s-' % service.pk)]
    if service.region_id == 'NW':
        return [name for name in namelist if name.startswith('%s_' % service.pk)]
    if service.region_id == 'GB':
        parts = service.pk.split('_')
        return [name for name in namelist if name.endswith('_%s_%s%s' % (parts[1], parts[0], suffix))]
    return [name for name in namelist if name.endswith('_%s%s' % (service.pk, suffix))]  # Wales


def get_pickle_filenames(service, path):
    """Given a Service and a folder path, return a list of filenames."""
    return get_filenames(service, path)


def get_files_from_zipfile(service):
    """Given a Service,
    return an iterable of open files from the relevant zipfile.
    """
    service_code = service.service_code
    if service.region_id == 'GB':
        archive_name = 'NCSD'
        parts = service_code.split('_')
        service_code = '_%s_%s' % (parts[-1], parts[-2])
    else:
        archive_name = service.region_id

    archive_path = os.path.join(settings.TNDS_DIR, archive_name + '.zip')

    try:
        with zipfile.ZipFile(archive_path) as archive:
            filenames = get_filenames(service, archive=archive)
            return [archive.open(filename) for filename in filenames]
    except (zipfile.BadZipfile, IOError, KeyError):
        return []


def timetable_from_service(service, day=None):
    """Given a Service, return a list of Timetables."""
    if day is None:
        day = date.today()

    if service.region_id == 'NI':
        path = os.path.join(settings.DATA_DIR, 'NI', service.pk + '.json')
        if os.path.exists(path):
            return northern_ireland.get_timetable(path, day)
        return []

    if service.region_id in {'UL', 'LE', 'MU', 'CO', 'FR'}:
        return gtfs.get_timetables(service.service_code, day)

    cache_key = '{}{}'.format(service.pk, day).replace(' ', '')
    timetables = cache.get(cache_key)
    if timetables is not None:
        return timetables
    timetables = (txc.Timetable(xml_file, day, service.description) for xml_file in get_files_from_zipfile(service))
    timetables = [timetable for timetable in timetables if hasattr(timetable, 'groupings')]
    if len(timetables) > 1:
        timetables = [timetable for timetable in timetables if timetable.groupings[0].rows[0].times] or timetables[:1]
    for timetable in timetables:
        for grouping in timetable.groupings:
            if grouping.rows and len(grouping.rows[0].times) > 100:
                service.show_timetable = False
                service.save()
                return
            del grouping.journeys
            del grouping.journeypatterns
            for row in grouping.rows:
                del row.next
        del timetable.journeypatterns
        del timetable.stops
        del timetable.operators
        del timetable.element
    cache.set(cache_key, timetables, None)
    return timetables

# coding=utf-8
import base64
import hashlib
import hmac
from urllib.parse import urlparse, urlencode
from django.conf import settings


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

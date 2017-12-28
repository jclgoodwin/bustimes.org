"""Tests for utilities"""
from django.test import TestCase
from .utils import sign_url, viglink


FIXTURES_DIR = './busstops/management/tests/fixtures/'


class UtilsTest(TestCase):
    def test_viglink(self):
        self.assertEqual(
            viglink('http://www.nationalexpress.com'),
            'http://redirect.viglink.com/?key=63dc39b879576a255e9dcee17b6c1929&u=http%3A%2F%2Fwww.nationalexpress.com'
        )

    def test_sign_url(self):
        self.assertRaises(Exception, sign_url)
        self.assertRaises(Exception, sign_url, 'fish.co.uk')
        self.assertRaises(Exception, sign_url, None, 'fish.co.uk')
        self.assertEqual(
            sign_url('http://example.com/?horse=1', 'fish'),
            'http://example.com/?horse=1&signature=s0RjLnH0GnQYwPTrUuoxZ1MfeRg='
        )

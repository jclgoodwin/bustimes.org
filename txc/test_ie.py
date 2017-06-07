from datetime import date
from django.test import TestCase
from . import ie


class TimetableTest(TestCase):
    def test_foo(self):
        ts = ie.get_timetable('buseireann-10-15-e16', date.today())
        for t in ts:
            print(t)
            print(t.groupings)

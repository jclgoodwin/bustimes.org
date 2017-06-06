from django.test import TestCase
from . import ie


class TimetableTest(TestCase):
    def test_foo(self):
        print(ie.get_timetable('buseireann-10-15-e16'))

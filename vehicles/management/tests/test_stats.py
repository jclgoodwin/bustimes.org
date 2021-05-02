from django.test import TestCase
from django.core.management import call_command


class StatsTest(TestCase):
    def test_stats(self):
        call_command('stats')
        call_command('timetable_source_stats')

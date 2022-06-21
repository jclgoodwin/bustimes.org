from django.test import TestCase
from django.core.management import call_command


class StatsTest(TestCase):
    def test_stats(self):
        response = self.client.get("/stats.json")
        self.assertEqual(response.json(), [])

        response = self.client.get("/timetable-source-stats.json")
        self.assertEqual(response.json(), [])

        call_command("stats")
        call_command("timetable_source_stats")

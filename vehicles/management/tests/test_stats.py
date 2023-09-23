from django.test import TestCase

from .. import tasks


class StatsTest(TestCase):
    def test_stats(self):
        response = self.client.get("/stats.json")
        self.assertEqual(response.json(), [])

        response = self.client.get("/timetable-source-stats.json")
        self.assertEqual(response.json(), [])

        tasks.stats()
        tasks.timetable_source_stats()

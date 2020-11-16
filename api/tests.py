from django.test import TestCase


class ApiTest(TestCase):
    def test_api(self):
        with self.assertNumQueries(4):
            response = self.client.get("/api/vehicles/", HTTP_ACCEPT="text/html")
        self.assertContains(response, "<title>Vehicle List – API – bustimes.org</title>")
        self.assertContains(response, "<a class='navbar-brand' href='/'>bustimes.org</a> ")

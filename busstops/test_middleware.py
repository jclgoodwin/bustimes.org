from django.test import TestCase


class WhiteNoiseWithFallbackMiddlewareTest(TestCase):
    def test_404_fallback(self):
        response = self.client.get("/static/css/style.p00p4nt5.css")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.headers["cache-control"],
            "max-age=0, no-cache, no-store, must-revalidate, private",
        )

    def test_404_no_fallback(self):
        response = self.client.get("/static/css/poo.p00p4nt5.css")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.headers["cache-control"],
            "max-age=0, no-cache, no-store, must-revalidate, private",
        )

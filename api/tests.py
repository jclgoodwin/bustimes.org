from django.test import TestCase


class ApiTest(TestCase):
    def test_api(self):
        with self.assertNumQueries(1):
            response = self.client.get(
                "/api/vehicles/",
            )

        self.assertEqual(response["Content-Type"], "application/json")

from django.test import TestCase
from .models import Region, Service


class MiddlewareTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.north = Region.objects.create(pk='N', name='North')
        cls.service = Service.objects.create(
            pk='ea_21-45-A-y08',
            line_name='45A',
            date='1984-01-01',
            region=cls.north
        )

    def test_found(self):
        response = self.client.get('/services/ea_21-45-A-y08')
        self.assertEqual(response.status_code, 200)

    def test_not_found(self):
        response = self.client.get('/services/1-45-A-y08-9')
        self.assertEqual(response.status_code, 404)

    def test_not_found_redirect(self):
        response = self.client.get('/services/21-45-A-y08-9')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/services/ea_21-45-A-y08')


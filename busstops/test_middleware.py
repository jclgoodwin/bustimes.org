from django.test import TestCase
from .models import Region, Service


class MiddlewareTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.north = Region.objects.create(pk='N', name='North')
        cls.service = Service.objects.create(
            service_code='ea_21-45-A-y08',
            line_name='45A',
            date='1984-01-01',
            region=cls.north
        )

    def test_found(self):
        response = self.client.get('/services/45a')
        self.assertEqual(response.status_code, 200)

    def test_not_found(self):
        response = self.client.get('/services/1-45-A-y08-9')
        self.assertEqual(response.status_code, 404)

    def test_not_found_redirect(self):
        response = self.client.get('/services/21-45-A-y08-9')
        self.assertRedirects(response, '/services/45a')

    def test_x_real_ip(self):
        response = self.client.get('/')
        self.assertEqual(response.wsgi_request.META['REMOTE_ADDR'], '127.0.0.1')

        response = self.client.get('/', HTTP_X_REAL_IP='6.6.6.6')
        self.assertEqual(response.wsgi_request.META['REMOTE_ADDR'], '6.6.6.6')

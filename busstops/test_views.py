from django.test import TestCase
from .models import Region, Operator, Service


class ViewsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.north = Region.objects.create(pk='N', name='North')
        cls.service = Service.objects.create(
            pk='ea_21-45-A-y08',
            line_name='45A',
            date='1984-01-01',
            region=cls.north
        )
        cls.chariots = Operator.objects.create(pk='AINS', name='Ainsley\'s Chariots', vehicle_mode='airline', region_id='N')
        cls.nuventure = Operator.objects.create(pk='VENT', name='Nu-Venture', vehicle_mode='bus', region_id='N')
        cls.service.operator.add(cls.chariots)

    def test_index(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['regions'][0], self.north)

    def test_not_found(self):
        response = self.client.get('/fff')
        self.assertEqual(response.status_code, 404)

    def test_static(self):
        for route in ('/cookies', '/data', '/map'):
            response = self.client.get(route)
            self.assertEqual(response.status_code, 200)

    def test_contact_get(self):
        response = self.client.get('/contact')
        self.assertEqual(response.status_code, 200)

    def test_contact_post(self):
        response = self.client.post('/contact')
        self.assertFalse(response.context['form'].is_valid())

    def test_region(self):
        response = self.client.get('/regions/N')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Chariots')
        self.assertNotContains(response, 'Nu-Venture')

    def test_operator_found(self):
        response = self.client.get('/operators/AINS')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Chariots')
        self.assertContains(response, 'An airline operator in')

    def test_operator_not_found(self):
        """An operator with no services should should return a 404 response"""
        response = self.client.get('/operators/VENT')
        self.assertEqual(response.status_code, 404)


from django.test import TestCase
from django.contrib.gis.geos import Point
from .models import Region, AdminArea, District, Locality, StopPoint, Operator, Service


class ViewsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.north = Region.objects.create(pk='N', name='North')
        cls.norfolk = AdminArea.objects.create(id=91, atco_code=91, region=cls.north, name='Norfolk')
        cls.north_norfolk = District.objects.create(id=91, admin_area=cls.norfolk, name='North Norfolk')
        cls.melton_constable = Locality.objects.create(id='E0048689', admin_area=cls.norfolk, name='Melton Constable')
        cls.inactive_stop = StopPoint.objects.create(
            pk='2900M115',
            common_name='Bus Shelter',
            active=False,
            admin_area=cls.norfolk,
            locality=cls.melton_constable,
            locality_centre=False,
            indicator='adj',
            bearing='E'
        )
        cls.stop = StopPoint.objects.create(
            pk='2900M114',
            common_name='Bus Shelter',
            active=True,
            admin_area=cls.norfolk,
            locality=cls.melton_constable,
            locality_centre=False,
            indicator='opp',
            bearing='W',
            latlong=Point(52.8566019427, 1.0331935468)
        )
        cls.inactive_service = Service.objects.create(
            pk='45A',
            line_name='45A',
            date='1984-01-01',
            region=cls.north,
            current=False
        )
        cls.inactive_service_with_alternative = Service.objects.create(
            pk='45B',
            line_name='45B',
            description='Holt - Norwich',
            date='1984-01-01',
            region=cls.north,
            current=False
        )
        cls.service = Service.objects.create(
            pk='ea_21-45-A-y08',
            line_name='45A',
            description='Holt - Norwich',
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
        self.assertContains(response, 'North')
        self.assertInHTML('<h1>North</h1>', response.content)
        self.assertInHTML('<a href="/areas/91">Norfolk</a>', response.content)
        self.assertContains(response, 'Chariots')
        self.assertNotContains(response, 'Nu-Venture')

    def test_admin_area(self):
        """Admin area containing just one child should redirect to that child"""
        response = self.client.get('/areas/91')
        self.assertRedirects(response, '/localities/E0048689')

    def test_district(self):
        """Admin area containing just one child should redirect to that child"""
        response = self.client.get('/districts/91')
        self.assertEqual(response.status_code, 200)

    def test_locality(self):
        response = self.client.get('/localities/E0048689')
        self.assertContains(response, '<h1>Melton Constable</h1>')

    def test_stops(self):
        response = self.client.get('/stops.json')
        self.assertEqual(response.status_code, 400)

        response = self.client.get('/stops.json', {
            'ymax': '52.9',
            'xmax': '1.1',
            'ymin': '52.8',
            'xmin': '1.0',
        })
        self.assertEqual(response.status_code, 200)


    def test_stop(self):
        response = self.client.get('/stops/2900M114')
        self.assertContains(response, 'North')
        self.assertContains(response, 'Norfolk')
        self.assertContains(response, 'Melton Constable, opp Bus Shelter')
        self.assertContains(response, 'heading=270')
        self.assertContains(response, 'leaflet.js')
        self.assertContains(response, 'map.js')

    def test_inactive_stop(self):
        response = self.client.get('/stops/2900M115')
        self.assertEqual(response.status_code, 404)

    def test_operator_found(self):
        response = self.client.get('/operators/AINS')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Chariots')
        self.assertContains(response, 'An airline operator in')

    def test_operator_not_found(self):
        """An operator with no services should should return a 404 response"""
        response = self.client.get('/operators/VENT')
        self.assertEqual(response.status_code, 404)

    def test_service(self):
        response = self.client.get('/services/ea_21-45-A-y08')
        self.assertEqual(response.status_code, 200)

    def test_service_redirect(self):
        response = self.client.get('/services/45B')
        self.assertEqual(response.status_code, 302)

    def test_service_not_found(self):
        response = self.client.get('/services/45A')
        self.assertEqual(response.status_code, 404)


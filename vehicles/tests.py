from freezegun import freeze_time
from django.test import TestCase
from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from busstops.models import DataSource, Region, Operator, Service
from .models import Vehicle, VehicleType, VehicleFeature, Livery, VehicleJourney, VehicleLocation, VehicleEdit
from . import admin


class VehiclesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.datetime = '2018-12-25 19:47+00:00'

        source = DataSource.objects.create(name='HP', datetime=cls.datetime)

        ea = Region.objects.create(id='EA', name='East Anglia')

        Operator.objects.create(region=ea, name='Bova and Over', id='BOVA', slug='bova-and-over')
        lynx = Operator.objects.create(region=ea, name='Lynx', id='LYNX', slug='lynx')

        tempo = VehicleType.objects.create(name='Optare Tempo', coach=False, double_decker=False)
        spectra = VehicleType.objects.create(name='Optare Spectra', coach=False, double_decker=True)

        service = Service.objects.create(service_code='49', region=ea, date='2018-12-25', tracking=True,
                                         description='Spixworth - Hunworth - Happisburgh')
        service.operator.add(lynx)

        cls.vehicle_1 = Vehicle.objects.create(fleet_number=1, reg='FD54JYA', vehicle_type=tempo, colours='#FF0000',
                                               notes='Trent Barton', operator=lynx)
        livery = Livery.objects.create(colours='#FF0000 #0000FF')
        cls.vehicle_2 = Vehicle.objects.create(code='99', fleet_number=50, reg='UWW2X', livery=livery,
                                               vehicle_type=spectra, operator=lynx)

        journey = VehicleJourney.objects.create(vehicle=cls.vehicle_1, datetime=cls.datetime, source=source,
                                                service=service, route_name='2')

        VehicleLocation.objects.create(datetime=cls.datetime, latlong=Point(0, 51), journey=journey, current=True)

    def test_vehicle(self):
        vehicle = Vehicle(reg='3990ME')
        self.assertEqual(str(vehicle), '3990 ME')
        self.assertIn('search/?text=3990ME%20or%20%223990%20ME%22&sort', vehicle.get_flickr_url())

        vehicle.reg = 'J122018'
        self.assertEqual(str(vehicle), 'J122018')

        vehicle = Vehicle(code='RML2604')
        self.assertIn('search/?text=RML2604&sort', vehicle.get_flickr_url())

        vehicle.operator = Operator(name='Lynx')
        self.assertIn('search/?text=Lynx%20RML2604&sort', vehicle.get_flickr_url())

        vehicle.operator.name = 'Stagecoach Oxenholme'
        self.assertIn('search/?text=Stagecoach%20RML2604&sort', vehicle.get_flickr_url())

    def test_vehicle_views(self):
        with self.assertNumQueries(2):
            response = self.client.get('/operators/bova-and-over/vehicles')
        self.assertEqual(404, response.status_code)
        self.assertFalse(str(response.context['exception']))

        with self.assertNumQueries(3):
            response = self.client.get('/operators/lynx/vehicles')
        self.assertTrue(response.context['code_column'])
        self.assertContains(response, '<td>99</td>')

        with self.assertNumQueries(4):
            response = self.client.get(self.vehicle_1.get_absolute_url() + '?date=poop')
        self.assertContains(response, 'Optare Tempo')
        self.assertContains(response, 'Trent Barton')
        self.assertContains(response, '#FF0000')

        with self.assertNumQueries(2):
            response = self.client.get(self.vehicle_2.get_absolute_url())
        self.assertEqual(404, response.status_code)
        self.assertFalse(str(response.context['exception']))

        with self.assertNumQueries(1):
            response = self.client.get('/journeys/1.json')
        self.assertEqual([], response.json())

    def test_feature(self):
        self.assertEqual('Wi-Fi', str(VehicleFeature(name='Wi-Fi')))

    def test_livery(self):
        livery = Livery(name='Go-Coach')
        self.assertEqual('Go-Coach', str(livery))
        self.assertIsNone(livery.preview())

        livery.colours = '#7D287D #FDEE00 #FDEE00'
        livery.horizontal = True
        self.assertEqual('<div style="height:1.5em;width:4em;background:linear-gradient' +
                         '(to top,#7D287D 34%,#FDEE00 34%)" title="Go-Coach"></div>', livery.preview())

        self.vehicle_1.livery = livery
        self.vehicle_1.livery.horizontal = False
        self.assertEqual('linear-gradient(to left,#7D287D 34%,#FDEE00 34%)',
                         self.vehicle_1.get_livery(179))
        self.assertIsNone(self.vehicle_1.get_text_colour())

        self.vehicle_1.livery.colours = '#c0c0c0'
        self.assertEqual('#c0c0c0', self.vehicle_1.get_livery(200))

    def test_vehicle_edit(self):
        url = self.vehicle_1.get_absolute_url() + '/edit'

        with self.assertNumQueries(5):
            response = self.client.get(url)
        self.assertNotContains(response, 'already')

        with self.assertNumQueries(6):
            response = self.client.post(url, {
                'fleet_number': '1',
                'reg': 'FD54JYA',
                'vehicle_type': self.vehicle_1.vehicle_type_id,
                'colours': '#FF0000',
                'notes': 'Trent Barton'
            })
        self.assertFalse(response.context['form'].has_changed())

        url = self.vehicle_2.get_absolute_url() + '/edit'

        with self.assertNumQueries(6):
            response = self.client.post(url, {
                'fleet_number': '50',
                'reg': 'UWW2X',
                'vehicle_type': self.vehicle_2.vehicle_type_id,
                'colours': self.vehicle_2.livery_id,
                'notes': ''
            })
        self.assertFalse(response.context['form'].has_changed())
        self.assertNotContains(response, 'already')

        self.assertEqual(0, VehicleEdit.objects.count())

        with self.assertNumQueries(5):
            response = self.client.post(url, {
                'fleet_number': '50',
                'reg': 'UWW 2X',
                'vehicle_type': self.vehicle_2.vehicle_type_id,
                'colours': self.vehicle_2.livery_id,
                'notes': 'Ex Ipswich Buses'
            })
        self.assertContains(response, 'Thank you')
        self.assertTrue(response.context['form'].has_changed())

        with self.assertNumQueries(5):
            response = self.client.get(url)

        self.assertContains(response, 'already')

        edit = VehicleEdit.objects.get()
        self.assertEqual('50 - UWW 2X', str(edit))
        self.assertEqual(self.vehicle_2.get_absolute_url(), edit.get_absolute_url())

        self.assertTrue(admin.VehicleEditAdmin.flickr(None, edit))
        self.assertEqual(admin.fleet_number(edit), '50')
        self.assertEqual(admin.reg(edit), 'UWW2X')
        self.assertEqual(str(admin.vehicle_type(edit)), 'Optare Spectra')
        edit.vehicle.vehicle_type = None
        self.assertEqual(str(admin.vehicle_type(edit)), '<ins>Optare Spectra</ins>')
        self.assertEqual(admin.notes(edit), '<ins>Ex Ipswich Buses</ins>')

    def test_vehicles_json(self):
        with freeze_time(self.datetime):
            with self.assertNumQueries(2):
                response = self.client.get('/vehicles.json?ymax=52&xmax=2&ymin=51&xmin=1')
        self.assertEqual(200, response.status_code)
        self.assertEqual({'type': 'FeatureCollection', 'features': []}, response.json())
        self.assertIsNone(response.get('last-modified'))

        with freeze_time(self.datetime):
            with self.assertNumQueries(2):
                response = self.client.get('/vehicles.json')
        vehicle = response.json()['features'][0]['properties']['vehicle']
        self.assertEqual(vehicle['name'], '1 - FD54 JYA')
        self.assertEqual(response.get('last-modified'), 'Tue, 25 Dec 2018 19:47:00 GMT')

    def test_location_json(self):
        location = VehicleLocation.objects.get()
        location.journey.vehicle = self.vehicle_2
        properties = location.get_json()['properties']
        vehicle = properties['vehicle']
        self.assertEqual(vehicle['name'], '50 - UWW 2X')
        self.assertEqual(vehicle['text_colour'], '#fff')
        self.assertFalse(vehicle['coach'])
        self.assertTrue(vehicle['decker'])
        self.assertEqual(vehicle['livery'], 'linear-gradient(to right,#FF0000 50%,#0000FF 50%)')
        self.assertNotIn('type', vehicle)
        self.assertNotIn('operator', properties)

        properties = location.get_json(True)['properties']
        vehicle = properties['vehicle']
        self.assertEqual(vehicle['type'], 'Optare Spectra')
        self.assertNotIn('decker', vehicle)
        self.assertNotIn('coach', vehicle)
        self.assertNotIn('operator', vehicle)
        self.assertEqual(properties['operator'], 'Lynx')

    def test_validation(self):
        vehicle = Vehicle(colours='ploop')
        with self.assertRaises(ValidationError):
            vehicle.clean()

        vehicle.colours = ''
        vehicle.clean()

    def test_big_map(self):
        with self.assertNumQueries(0):
            response = self.client.get('/vehicles')
        self.assertContains(response, 'bigmap.min.js')

    def test_dashboard(self):
        with self.assertNumQueries(2):
            response = self.client.get('/vehicle-tracking-report')
        self.assertContains(response, 'Vehicle tracking report')
        self.assertContains(response, '<a href="/services/spixworth-hunworth-happisburgh/vehicles">Yes</a>*')

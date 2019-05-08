from freezegun import freeze_time
from django.test import TestCase
from django.contrib.gis.geos import Point
from busstops.models import DataSource
from .models import Vehicle, VehicleJourney, VehicleLocation


class VehiclesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.datetime = '2018-12-25 19:47+00:00'
        source = DataSource.objects.create(name='HP', datetime=cls.datetime)
        cls.vehicle_1 = Vehicle.objects.create(fleet_number=1, reg='FD54JYA')
        cls.vehicle_2 = Vehicle.objects.create(fleet_number=50, reg='UWW2X', colours='#FF0000 #0000FF')
        journey = VehicleJourney.objects.create(vehicle=cls.vehicle_1, datetime=cls.datetime, source=source)
        VehicleLocation.objects.create(datetime=cls.datetime, latlong=Point(0, 51), journey=journey, current=True)

    def test_vehicle(self):
        vehicle = Vehicle(reg='3990ME')
        self.assertEqual(str(vehicle), '3990 ME')

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
        self.assertEqual(response.json()['features'][0]['properties']['vehicle']['name'], '1 - FD54 JYA')
        self.assertEqual(response.get('last-modified'), 'Tue, 25 Dec 2018 19:47:00 GMT')

    def test_location_json(self):
        location = VehicleLocation.objects.get()
        location.journey.vehicle = self.vehicle_2
        json = location.get_json(True)
        self.assertEqual(json['properties']['vehicle']['name'], '50 - UWW 2X')
        self.assertEqual(json['properties']['vehicle']['text_colour'], '#fff')
        self.assertEqual(json['properties']['vehicle']['livery'], 'linear-gradient(to right,#FF0000 50%,#0000FF 50%)')

    @freeze_time('4 July 1940')
    def test_vehicle_detail(self):
        vehicle = Vehicle.objects.get(fleet_number='50')
        with self.assertNumQueries(2):
            response = self.client.get(vehicle.get_absolute_url() + '?date=poo poo pants')
        self.assertEqual(response.status_code, 404)

    def test_dashboard(self):
        with self.assertNumQueries(1):
            response = self.client.get('/vehicle-tracking-report')
        self.assertContains(response, 'Vehicle tracking report')

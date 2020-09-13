from freezegun import freeze_time
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from busstops.models import DataSource, Region, Operator, Service
from .models import (Vehicle, VehicleType, VehicleFeature, Livery,
                     VehicleJourney, VehicleLocation, VehicleEdit, VehicleRevision)
from . import admin


@override_settings(CELERY_BROKER_URL='redis://localhost:69')
class VehiclesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.datetime = '2018-12-25 19:47+00:00'

        source = DataSource.objects.create(name='HP', datetime=cls.datetime)

        ea = Region.objects.create(id='EA', name='East Anglia')

        cls.wifi = VehicleFeature.objects.create(name='Wi-Fi')
        cls.usb = VehicleFeature.objects.create(name='USB')

        cls.bova = Operator.objects.create(region=ea, name='Bova and Over', id='BOVA', slug='bova-and-over',
                                           parent='Madrigal Electromotive')
        cls.lynx = Operator.objects.create(region=ea, name='Lynx', id='LYNX', slug='lynx',
                                           parent='Madrigal Electromotive')

        tempo = VehicleType.objects.create(name='Optare Tempo', coach=False, double_decker=False)
        spectra = VehicleType.objects.create(name='Optare Spectra', coach=False, double_decker=True)

        service = Service.objects.create(service_code='49', region=ea, date='2018-12-25', tracking=True,
                                         description='Spixworth - Hunworth - Happisburgh')
        service.operator.add(cls.lynx)
        service.operator.add(cls.bova)

        cls.vehicle_1 = Vehicle.objects.create(code='2', fleet_number=1, reg='FD54JYA', vehicle_type=tempo,
                                               colours='#FF0000', notes='Trent Barton', operator=cls.lynx)
        livery = Livery.objects.create(colours='#FF0000 #0000FF')
        cls.vehicle_2 = Vehicle.objects.create(code='50', fleet_number=50, reg='UWW2X', livery=livery,
                                               vehicle_type=spectra, operator=cls.lynx, data={'Depot': 'Long Sutton'})

        cls.journey = VehicleJourney.objects.create(vehicle=cls.vehicle_1, datetime=cls.datetime, source=source,
                                                    service=service, route_name='2')

        cls.location = VehicleLocation.objects.create(datetime=cls.datetime, latlong=Point(0, 51),
                                                      journey=cls.journey, current=True)
        cls.vehicle_1.latest_location = cls.location
        cls.vehicle_1.save()

        cls.vehicle_1.features.set([cls.wifi])

        cls.user = User.objects.create(username='josh', is_staff=True, is_superuser=True)

    def test_parent(self):
        response = self.client.get('/groups/Madrigal Electromotive/vehicles')
        self.assertContains(response, 'Lynx')
        self.assertContains(response, 'Madrigal Electromotive')
        self.assertContains(response, 'Optare')

    def test_vehicle(self):
        vehicle = Vehicle(reg='3990ME')
        self.assertEqual(str(vehicle), '3990\xa0ME')
        self.assertIn('search/?text=3990ME%20or%20%223990%20ME%22&sort', vehicle.get_flickr_url())

        vehicle.reg = 'J122018'
        self.assertEqual(str(vehicle), 'J122018')
        self.assertTrue(vehicle.editable())

        vehicle.notes = 'Spare ticket machine'
        self.assertEqual('', vehicle.get_flickr_link())
        self.assertFalse(vehicle.editable())

        vehicle = Vehicle(code='RML2604')
        self.assertIn('search/?text=RML2604&sort', vehicle.get_flickr_url())

        vehicle.operator = Operator(name='Lynx')
        self.assertIn('search/?text=Lynx%20RML2604&sort', vehicle.get_flickr_url())

        vehicle.fleet_number = '11111'
        self.assertIn('search/?text=Lynx%2011111&sort', vehicle.get_flickr_url())

        vehicle.reg = 'YN69GHA'
        vehicle.operator.parent = 'Stagecoach'
        vehicle.fleet_number = '11111'

        self.assertIn('search/?text=YN69GHA%20or%20%22YN69%20GHA%22%20or%20Stagecoach%2011111&sort',
                      vehicle.get_flickr_url())

        vehicle.code = 'YN_69_GHA'
        self.assertFalse(vehicle.fleet_number_mismatch())
        vehicle.code = 'YN19GHA'
        self.assertTrue(vehicle.fleet_number_mismatch())

    def test_fleet_lists(self):
        with self.assertNumQueries(2):
            response = self.client.get('/operators/bova-and-over/vehicles')
        self.assertEqual(404, response.status_code)
        self.assertFalse(str(response.context['exception']))

        # last seen today - should only show time
        with freeze_time('2018-12-25 19:50+00:00'):
            with self.assertNumQueries(4):
                response = self.client.get('/operators/lynx/vehicles')
        self.assertNotContains(response, '25 Dec')
        self.assertContains(response, '19:47')

        # last seen today - should only show time
        with freeze_time('2018-12-26 12:00+00:00'):
            with self.assertNumQueries(4):
                response = self.client.get('/operators/lynx/vehicles')
        self.assertContains(response, '25 Dec 19:47')

        self.assertTrue(response.context['code_column'])
        self.assertContains(response, '<td class="number">2</td>')

    def test_vehicle_views(self):
        with self.assertNumQueries(8):
            response = self.client.get(self.vehicle_1.get_absolute_url() + '?date=poop')
        self.assertContains(response, 'Optare Tempo')
        self.assertContains(response, 'Trent Barton')
        self.assertContains(response, '#FF0000')

        with self.assertNumQueries(7):
            response = self.client.get(self.vehicle_2.get_absolute_url())
        self.assertEqual(200, response.status_code)

        with self.assertNumQueries(0):
            response = self.client.get('/journeys/1.json')
        self.assertEqual([], response.json())

    def test_livery(self):
        livery = Livery(name='Go-Coach')
        self.assertEqual('Go-Coach', str(livery))
        self.assertIsNone(livery.preview())

        livery.colours = '#7D287D #FDEE00 #FDEE00'
        livery.horizontal = True
        self.assertEqual('<div style="height:1.5em;width:2.25em;background:linear-gradient' +
                         '(to top,#7D287D 34%,#FDEE00 34%)" title="Go-Coach"></div>', livery.preview())
        livery.horizontal = False
        livery.angle = 45
        self.assertEqual('linear-gradient(45deg,#7D287D 34%,#FDEE00 34%)', livery.get_css())
        self.assertEqual('linear-gradient(315deg,#7D287D 34%,#FDEE00 34%)', livery.get_css(10))
        self.assertEqual('linear-gradient(45deg,#7D287D 34%,#FDEE00 34%)', livery.get_css(300))

        livery.angle = None
        self.vehicle_1.livery = livery
        self.assertEqual('linear-gradient(to left,#7D287D 34%,#FDEE00 34%)',
                         self.vehicle_1.get_livery(179))
        self.assertIsNone(self.vehicle_1.get_text_colour())

        self.vehicle_1.livery.colours = '#c0c0c0'
        self.assertEqual('#c0c0c0', self.vehicle_1.get_livery(200))

        livery.css = 'linear-gradient(45deg,#ED1B23 35%,#fff 35%,#fff 45%,#ED1B23 45%)'
        self.assertEqual(livery.get_css(), 'linear-gradient(45deg,#ED1B23 35%,#fff 35%,#fff 45%,#ED1B23 45%)')
        self.assertEqual(livery.get_css(0), 'linear-gradient(315deg,#ED1B23 35%,#fff 35%,#fff 45%,#ED1B23 45%)')
        self.assertEqual(livery.get_css(10), 'linear-gradient(315deg,#ED1B23 35%,#fff 35%,#fff 45%,#ED1B23 45%)')
        self.assertEqual(livery.get_css(180), 'linear-gradient(45deg,#ED1B23 35%,#fff 35%,#fff 45%,#ED1B23 45%)')
        self.assertEqual(livery.get_css(181), 'linear-gradient(45deg,#ED1B23 35%,#fff 35%,#fff 45%,#ED1B23 45%)')

    def test_vehicle_edit_1(self):
        self.client.force_login(self.user)

        url = self.vehicle_1.get_absolute_url() + '/edit'

        with self.assertNumQueries(13):
            response = self.client.get(url)
        self.assertNotContains(response, 'already')
        self.assertContains(response, '<datalist id="depots"><option value="Long Sutton"></datalist>', html=True)

        # edit nothing
        with self.assertNumQueries(16):
            response = self.client.post(url, {
                'fleet_number': '1',
                'reg': 'FD54JYA',
                'vehicle_type': self.vehicle_1.vehicle_type_id,
                'features': self.wifi.id,
                'operator': self.lynx.id,
                'colours': '#FF0000',
                'other_colour': '#ffffff',
                'notes': 'Trent Barton',
            })
        self.assertFalse(response.context['form'].has_changed())
        self.assertNotContains(response, 'already')

        # edit fleet number
        with self.assertNumQueries(12):
            response = self.client.post(url, {
                'fleet_number': '2',
                'reg': 'FD54JYA',
                'vehicle_type': self.vehicle_1.vehicle_type_id,
                'features': self.wifi.id,
                'operator': self.lynx.id,
                'colours': '#FF0000',
                'other_colour': '#FF0000',
                'notes': 'Trent Barton',
            })
        self.assertIsNone(response.context['form'])
        self.assertContains(response, 'I’ll update those details')

        edit = VehicleEdit.objects.filter(approved=None).get()
        self.assertEqual(edit.colours, '')
        self.assertEqual(edit.get_changes(), {
            'fleet_number': '2'
        })

        # # edit reg, colour
        # with self.assertNumQueries(14):
        #     response = self.client.post(url, {
        #         'fleet_number': '1',
        #         'reg': 'K292JVF',
        #         'vehicle_type': self.vehicle_1.vehicle_type_id,
        #         'features': self.wifi.id,
        #         'operator': self.lynx.id,
        #         'colours': 'Other',
        #         'other_colour': '#ffffff',
        #         'notes': 'Trent Barton',
        #     })
        # self.assertIsNone(response.context['form'])
        # self.assertContains(response, 'I’ll update the other details')

        # self.assertEqual(2, VehicleEdit.objects.filter(approved=None).count())

        # response = self.client.get('/admin/vehicles/vehicleedit/')
        # self.assertContains(response, 'Lynx (2)')
        # self.assertContains(response, '127.0.0.1 (2)')
        # self.assertContains(response, 'Wi-Fi')
        # self.assertNotContains(response, '<del>Wi-Fi</del>')

        # edit type, livery and name with bad URL
        with self.assertNumQueries(16):
            response = self.client.post(url, {
                'fleet_number': '1',
                'reg': 'K292JVF',
                'vehicle_type': self.vehicle_2.vehicle_type_id,
                'features': self.wifi.id,
                'operator': self.lynx.id,
                'colours': self.vehicle_2.livery_id,
                'other_colour': '#ffffff',
                'notes': 'Trent Barton',
                'name': 'Colin',
                'url': 'http://localhost'
            })
        self.assertTrue(response.context['form'].has_changed())
        self.assertContains(response, 'That URL does')
        self.assertContains(response, '/edit-vehicle.')

#         # edit type, livery, name and feature
#         with self.assertNumQueries(16):
#             response = self.client.post(url, {
#                 'fleet_number': '1',
#                 'reg': 'K292JVF',
#                 'vehicle_type': self.vehicle_2.vehicle_type_id,
#                 'features': self.usb.id,
#                 'operator': self.lynx.id,
#                 'colours': self.vehicle_2.livery_id,
#                 'other_colour': '#ffffff',
#                 'notes': 'Trent Barton',
#                 'name': 'Colin',
#                 'url': 'https://bustimes.org'
#             })
#         self.assertIsNone(response.context['form'])
#         self.assertContains(response, 'I’ll update those details')
#         self.assertNotContains(response, '/edit-vehicle.')
#         edit = VehicleEdit.objects.last()
#         self.assertEqual(edit.url, 'https://bustimes.org')
#         self.assertEqual(str(edit.get_changes()), "{'vehicle_type': 'Optare Spectra', 'name': 'Colin', 'features': \
# [<VehicleEditFeature: <del>Wi-Fi</del>>, <VehicleEditFeature: <ins>USB</ins>>]}")

#         response = self.client.get('/admin/vehicles/vehicleedit/')
#         self.assertContains(response, '<del>Wi-Fi</del>')

        # should not create an edit
        with self.assertNumQueries(16):
            response = self.client.post(url, {
                'fleet_number': '',
                'reg': 'K292JVF',
                'vehicle_type': self.vehicle_1.vehicle_type_id,
                'features': self.wifi.id,
                'operator': self.lynx.id,
                'colours': '#FFFF00',
                'other_colour': '#ffffff',
                'notes': 'Trent Barton',
            })
        self.assertTrue(response.context['form'].has_changed())
        self.assertContains(response, 'Select a valid choice. #FFFF00 is not one of the available choices')
        self.assertContains(response, 'already')

        # self.assertEqual(3, VehicleEdit.objects.filter(approved=None).count())

        # with self.assertNumQueries(12):
        #     admin.apply_edits(VehicleEdit.objects.select_related('vehicle'))
        # self.assertEqual(0, VehicleEdit.objects.filter(approved=None).count())
        # vehicle = Vehicle.objects.get(notes='Trent Barton')
        # self.assertEqual(vehicle.reg, 'K292JVF')
        # self.assertEqual(vehicle.name, 'Colin')
        # self.assertEqual(self.usb, vehicle.features.get())
        # self.assertEqual(str(vehicle.vehicle_type), 'Optare Spectra')
        # self.assertEqual(vehicle.fleet_number, 2)

        # with self.assertNumQueries(10):
        #     response = self.client.get('/admin/vehicles/vehicleedit/?username=1')
        # self.assertNotContains(response, 'Lynx')
        # self.assertEqual(3, response.context_data['cl'].result_count)

        # response = self.client.get('/admin/vehicles/vehicleedit/?change=colours')
        # self.assertEqual(2, response.context_data['cl'].result_count)

        # response = self.client.get('/admin/vehicles/vehicleedit/?change=changes__Depot')
        # self.assertEqual(0, response.context_data['cl'].result_count)

        # response = self.client.get('/admin/vehicles/vehicleedit/?change=reg')
        # self.assertEqual(0, response.context_data['cl'].result_count)

    def test_vehicle_edit_2(self):
        self.client.force_login(self.user)

        url = self.vehicle_2.get_absolute_url() + '/edit'

        with self.assertNumQueries(15):
            response = self.client.post(url, {
                'fleet_number': '50',
                'reg': 'UWW2X',
                'vehicle_type': self.vehicle_2.vehicle_type_id,
                'operator': self.lynx.id,
                'colours': self.vehicle_2.livery_id,
                'other_colour': '#ffffff',
                'notes': '',
                'depot': 'Long Sutton'
            })
        self.assertTrue(response.context['form'].fields['fleet_number'].disabled)
        self.assertFalse(response.context['form'].has_changed())
        self.assertNotContains(response, 'already')

        self.assertEqual(0, VehicleEdit.objects.count())

        self.assertNotContains(response, '/operators/bova-and-over')

        with self.assertNumQueries(13):
            response = self.client.post(url, {
                'fleet_number': '50',
                'reg': '',
                'vehicle_type': self.vehicle_2.vehicle_type_id,
                'operator': self.bova.id,
                'colours': self.vehicle_2.livery_id,
                'other_colour': '#ffffff',
                'notes': 'Ex Ipswich Buses',
                'depot': 'Holt',
                'name': 'Luther Blisset',
                'branding': 'Coastliner',
            })
        self.assertIsNone(response.context['form'])

        # check vehicle operator has been changed
        self.assertContains(response, '/operators/bova-and-over')
        self.assertContains(response, 'Changed operator from Lynx to Bova and Over')
        self.assertContains(response, 'Changed depot from Long Sutton to Holt')
        self.assertContains(response, '<p>I’ll update the other details shortly</p>')

        response = self.client.get('/vehicles/history')
        self.assertContains(response, '<td>operator</td>')
        self.assertContains(response, '<td>Lynx</td>')
        self.assertContains(response, '<td>Bova and Over</td>')

        revision = response.context['revisions'][0]
        self.assertEqual(revision.from_operator, self.lynx)
        self.assertEqual(revision.to_operator, self.bova)
        self.assertEqual(str(revision), 'operator: Lynx → Bova and Over, depot: Long Sutton → Holt')

        response = self.client.get(f'{self.vehicle_2.get_absolute_url()}/history')
        self.assertContains(response, '<td>operator</td>')
        self.assertContains(response, '<td>Lynx</td>')
        self.assertContains(response, '<td>Bova and Over</td>')

        with self.assertNumQueries(13):
            response = self.client.get(url)
        self.assertContains(response, 'already')

        # edit = VehicleEdit.objects.get()
        # self.assertEqual(edit.get_changes(), {'branding': 'Coastliner', 'name': 'Luther Blisset',
        #                                       'notes': 'Ex Ipswich Buses'})

        # self.assertTrue(str(edit).isdigit())
        # self.assertEqual(self.vehicle_2.get_absolute_url(), edit.get_absolute_url())

        # self.assertTrue(admin.VehicleEditAdmin.flickr(None, edit))
        # self.assertEqual(admin.fleet_number(edit), '50')
        # # self.assertEqual(admin.reg(edit), '<del>UWW2X</del>')
        # self.assertEqual(admin.notes(edit), '<ins>Ex Ipswich Buses</ins>')

        # self.assertEqual(str(admin.vehicle_type(edit)), 'Optare Spectra')
        # edit.vehicle_type = 'Ford Transit'
        # self.assertEqual(str(admin.vehicle_type(edit)), '<del>Optare Spectra</del><br><ins>Ford Transit</ins>')
        # edit.vehicle.vehicle_type = None
        # self.assertEqual(admin.vehicle_type(edit), '<ins>Ford Transit</ins>')

    def test_vehicles_edit(self):
        self.client.force_login(self.user)

        with self.assertNumQueries(12):
            response = self.client.post('/operators/lynx/vehicles/edit')
        self.assertContains(response, 'Select vehicles to update')
        self.assertFalse(VehicleEdit.objects.all())

        with self.assertNumQueries(16):
            response = self.client.post('/operators/lynx/vehicles/edit', {
                'vehicle': self.vehicle_1.id,
                'operator': self.lynx.id,
                'notes': 'foo'
            })
        self.assertContains(response, 'I’ll update those details (1 vehicle) shortly')
        edit = VehicleEdit.objects.get()
        self.assertEqual(edit.vehicle_type, '')
        self.assertEqual(edit.notes, 'foo')

        self.assertContains(response, 'FD54\xa0JYA')

        # just updating operator should not create a VehicleEdit, but update the vehicle immediately
        with self.assertNumQueries(18):
            response = self.client.post('/operators/lynx/vehicles/edit', {
                'vehicle': self.vehicle_1.id,
                'operator': self.bova.id,
            })
        self.assertNotContains(response, 'FD54\xa0JYA')
        self.vehicle_1.refresh_from_db()
        self.assertEqual(self.bova, self.vehicle_1.operator)
        self.assertContains(response, '1 vehicle updated')
        self.assertEqual(1, VehicleEdit.objects.count())

    def test_vehicles_json(self):
        with freeze_time(self.datetime):
            with self.assertNumQueries(1):
                response = self.client.get('/vehicles.json?ymax=52&xmax=2&ymin=51&xmin=1')
            self.assertEqual(200, response.status_code)
            self.assertEqual({'type': 'FeatureCollection', 'features': []}, response.json())
            self.assertIsNone(response.get('last-modified'))

            with self.assertNumQueries(1):
                response = self.client.get('/vehicles.json')
            features = response.json()['features']
            self.assertEqual(features[0]['properties']['vehicle']['name'], '1 - FD54\xa0JYA')
            self.assertEqual(features[0]['properties']['service'],
                             {'line_name': '', 'url': '/services/spixworth-hunworth-happisburgh'})

            # self.assertEqual(response.get('last-modified'), 'Tue, 25 Dec 2018 19:47:00 GMT')

            VehicleJourney.objects.update(service=None)
            with self.assertNumQueries(1):
                response = self.client.get('/vehicles.json')
            features = response.json()['features']
            self.assertEqual(features[0]['properties']['vehicle']['name'], '1 - FD54\xa0JYA')
            self.assertEqual(features[0]['properties']['service'], {'line_name': '2'})

    def test_location_json(self):
        location = VehicleLocation.objects.get()
        location.journey.vehicle = self.vehicle_2
        properties = location.get_json()['properties']
        vehicle = properties['vehicle']
        self.assertEqual(vehicle['name'], '50 - UWW\xa02X')
        self.assertEqual(vehicle['text_colour'], '#fff')
        self.assertFalse(vehicle['coach'])
        self.assertTrue(vehicle['decker'])
        self.assertEqual(vehicle['livery'], 'linear-gradient(to right,#FF0000 50%,#0000FF 50%)')
        self.assertNotIn('type', vehicle)
        self.assertNotIn('operator', properties)

        properties = location.get_json(True)['properties']
        vehicle = properties['vehicle']
        self.assertTrue(vehicle['decker'])
        self.assertFalse(vehicle['coach'])
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
            self.client.get('/map')

    def test_vehicles(self):
        with self.assertNumQueries(1):
            self.client.get('/vehicles')

    def test_journey_detail(self):
        with self.assertNumQueries(2):
            response = self.client.get(f'/journeys/{self.journey.id}')
        self.assertContains(response, '<th colspan="2"></th><th>Timetable</th><th>Live</th></tr>')

    def test_location_detail(self):
        with self.assertNumQueries(1):
            response = self.client.get(f'/vehicles/locations/{self.location.id}')
        self.assertContains(response, '<a href="/services/spixworth-hunworth-happisburgh"> </a>', html=True)

    def test_service_vehicle_history(self):
        with self.assertNumQueries(4):
            response = self.client.get('/services/spixworth-hunworth-happisburgh/vehicles?date=poop')
        self.assertContains(response, 'Vehicles')
        self.assertContains(response, '/vehicles/')
        self.assertContains(response, '<option selected value="2018-12-25">Tuesday 25 December 2018</option>')
        self.assertContains(response, '1 - FD54\xa0JYA')

        with self.assertNumQueries(4):
            response = self.client.get('/services/spixworth-hunworth-happisburgh/vehicles?date=2004-04-04')
        self.assertNotContains(response, '1 - FD54\xa0JYA')

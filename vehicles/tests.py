import time_machine
from django.test import TestCase, override_settings
from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from accounts.models import User
from busstops.models import DataSource, Region, Operator, Service
from .models import (Vehicle, VehicleType, VehicleFeature, Livery,
                     VehicleJourney, VehicleLocation, VehicleEdit, VehicleRevision)


class VehiclesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.datetime = '2020-10-19 23:47+00:00'

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
                                               colours='#FF0000', notes='Trent Barton', operator=cls.lynx,
                                               data={'Depot': 'Holt'})
        livery = Livery.objects.create(colours='#FF0000 #0000FF')
        cls.vehicle_2 = Vehicle.objects.create(code='50', fleet_number=50, reg='UWW2X', livery=livery,
                                               vehicle_type=spectra, operator=cls.lynx, data={'Depot': 'Long Sutton'})

        cls.journey = VehicleJourney.objects.create(vehicle=cls.vehicle_1, datetime=cls.datetime, source=source,
                                                    service=service, route_name='2')

        cls.location = VehicleLocation.objects.create(datetime=cls.datetime, latlong=Point(0, 51),
                                                      journey=cls.journey, current=True)
        # cls.vehicle_1.latest_location = cls.location
        cls.vehicle_1.latest_journey = cls.journey
        cls.vehicle_1.save()

        cls.vehicle_1.features.set([cls.wifi])

        cls.user = User.objects.create(username='josh', is_staff=True, is_superuser=True, email='j@example.com')
        cls.trusted_user = User.objects.create(username='norma', trusted=True, email='n@example.com')
        cls.untrusted_user = User.objects.create(username='clem', trusted=False, email='c@example.com')

    def test_untrusted_user(self):
        self.client.force_login(self.untrusted_user)

        with self.assertNumQueries(2):
            response = self.client.get(self.vehicle_1.get_absolute_url() + '/edit')
        self.assertEqual(response.status_code, 403)

        with self.assertNumQueries(3):
            response = self.client.get('/operators/lynx/vehicles/edit')
        self.assertEqual(response.status_code, 403)

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
        with time_machine.travel('2020-10-20 12:00+01:00'):
            with self.assertNumQueries(2):
                response = self.client.get('/operators/lynx/vehicles')
        self.assertNotContains(response, '20 Oct')
        self.assertContains(response, '00:47')

        # last seen yesterday - should show date
        with time_machine.travel('2020-10-21 00:10+01:00'):
            with self.assertNumQueries(2):
                response = self.client.get('/operators/lynx/vehicles')
        self.assertContains(response, '20 Oct 00:47')

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

        # can't connect to redis - no drama
        with override_settings(REDIS_URL='redis://localhose:69'):
            with self.assertNumQueries(1):
                response = self.client.get(f'/journeys/{self.journey.id}.json')
        self.assertEqual({}, response.json())

        self.journey.refresh_from_db()
        self.assertEqual(str(self.journey), '19 Oct 20 23:47 2  ')
        self.assertEqual(
            self.journey.get_absolute_url(),
            f'/vehicles/{self.vehicle_1.id}?date=2020-10-19#journeys/{self.journey.id}'
        )

        self.location.refresh_from_db()
        self.assertEqual(str(self.location), '19 Oct 2020 23:47:00')

    def test_search(self):
        response = self.client.get('/search?q=fd54jya')
        self.assertContains(response, '1 vehicle')

    def test_livery(self):
        livery = Livery(name='Go-Coach')
        self.assertEqual('Go-Coach', str(livery))
        self.assertIsNone(livery.preview())

        livery.colours = '#7D287D #FDEE00 #FDEE00'
        livery.horizontal = True
        livery.save()
        self.assertEqual('<div style="height:1.5em;width:2.25em;background:linear-gradient' +
                         '(to top,#7D287D 34%,#FDEE00 34%)" title="Go-Coach"></div>', livery.preview())
        livery.horizontal = False
        livery.angle = 45
        livery.save()
        self.assertEqual('linear-gradient(45deg,#7D287D 34%,#FDEE00 34%)', livery.left_css)
        self.assertEqual('linear-gradient(315deg,#7D287D 34%,#FDEE00 34%)', livery.right_css)

        livery.angle = None
        livery.save()
        self.vehicle_1.livery = livery
        self.assertEqual('linear-gradient(to left,#7D287D 34%,#FDEE00 34%)',
                         self.vehicle_1.get_livery(179))
        self.assertIsNone(self.vehicle_1.get_text_colour())

        self.vehicle_1.livery.colours = '#c0c0c0'
        self.vehicle_1.livery.save()
        self.assertEqual('#c0c0c0', self.vehicle_1.get_livery(200))

        livery.css = 'linear-gradient(45deg,#ED1B23 35%,#fff 35%,#fff 45%,#ED1B23 45%)'
        livery.set_css()
        self.assertEqual(livery.left_css, 'linear-gradient(45deg,#ED1B23 35%,#fff 35%,#fff 45%,#ED1B23 45%)')
        self.assertEqual(livery.right_css, 'linear-gradient(315deg,#ED1B23 35%,#fff 35%,#fff 45%,#ED1B23 45%)')

    def test_vehicle_edit_1(self):
        url = self.vehicle_1.get_absolute_url() + '/edit'

        with self.assertNumQueries(0):
            response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f'/accounts/login/?next={url}')

        with self.assertNumQueries(0):
            response = self.client.get(response.url)
        self.assertContains(response, '<p>To edit vehicle details, please log in.</p>')

        self.client.force_login(self.user)

        with self.assertNumQueries(12):
            response = self.client.get(url)
        self.assertNotContains(response, 'already')
        self.assertContains(response, '<option value="Holt" selected>Holt</option>')

        initial = {
            'fleet_number': '1',
            'reg': 'FD54JYA',
            'vehicle_type': self.vehicle_1.vehicle_type_id,
            'features': self.wifi.id,
            'operator': self.lynx.id,
            'colours': '#FF0000',
            'other_colour': '#ffffff',
            'notes': 'Trent Barton',
            'depot': 'Holt'
        }

        # edit nothing
        with self.assertNumQueries(15):
            response = self.client.post(url, initial)
        self.assertFalse(response.context['form'].has_changed())
        self.assertNotContains(response, 'already')

        # edit fleet number
        initial['fleet_number'] = '2'
        with self.assertNumQueries(12):
            response = self.client.post(url, initial)
        self.assertIsNone(response.context['form'])
        self.assertContains(response, 'I’ll update those details')

        edit = VehicleEdit.objects.filter(approved=None).get()
        self.assertEqual(edit.colours, '')
        self.assertEqual(edit.get_changes(), {
            'fleet_number': '2'
        })

        # edit type, livery and name with bad URL
        initial['vehicle_type'] = self.vehicle_2.vehicle_type_id
        initial['colours'] = self.vehicle_2.livery_id
        initial['name'] = 'Colin'
        initial['url'] = 'http://localhost'
        with self.assertNumQueries(15):
            response = self.client.post(url, initial)
        self.assertTrue(response.context['form'].has_changed())
        self.assertContains(response, 'That URL does')
        self.assertContains(response, '/edit-vehicle.')

        response = self.client.get('/admin/vehicles/vehicleedit/')
        self.assertContains(response, '<td class="field-reg">FD54JYA</td>')
        self.assertContains(response, '<td class="field-vehicle_type">Optare Tempo</td>')

        # should not create an edit
        with self.assertNumQueries(15):
            initial['colours'] = '#FFFF00'
            response = self.client.post(url, initial)
        self.assertTrue(response.context['form'].has_changed())
        self.assertContains(response, 'Select a valid choice. #FFFF00 is not one of the available choices')
        self.assertContains(response, 'already')

        self.assertEqual(1, VehicleEdit.objects.all().count())

        response = self.client.get('/admin/accounts/user/')
        self.assertContains(
            response,
            '<td class="field-approved">'
            f'<a href="/admin/vehicles/vehicleedit/?user={self.user.id}&approved__exact=1">0</a></td>'
            '<td class="field-disapproved">'
            f'<a href="/admin/vehicles/vehicleedit/?user={self.user.id}&approved__exact=0">0</a></td>'
            '<td class="field-pending">'
            f'<a href="/admin/vehicles/vehicleedit/?user={self.user.id}&approved__isnull=True">1</a></td>'
        )

        with self.assertNumQueries(9):
            response = self.client.get('/admin/vehicles/vehicleedit/')
        self.assertContains(response, '<del>1</del><br><ins>2</ins>')
        self.assertEqual(1, response.context_data['cl'].result_count)

    def test_vehicle_edit_2(self):
        self.client.force_login(self.user)

        url = self.vehicle_2.get_absolute_url() + '/edit'

        initial = {
            'fleet_number': '50',
            'reg': 'UWW2X',
            'vehicle_type': self.vehicle_2.vehicle_type_id,
            'operator': self.lynx.id,
            'colours': self.vehicle_2.livery_id,
            'other_colour': '#ffffff',
            'notes': '',
            'depot': 'Long Sutton'
        }

        with self.assertNumQueries(14):
            response = self.client.post(url, initial)
        self.assertTrue(response.context['form'].fields['fleet_number'].disabled)
        self.assertFalse(response.context['form'].has_changed())
        self.assertNotContains(response, 'already')

        self.assertEqual(0, VehicleEdit.objects.count())

        self.assertNotContains(response, '/operators/bova-and-over')

        initial['notes'] = 'Ex Ipswich Buses'
        initial['depot'] = ''
        initial['name'] = 'Luther Blisset'
        initial['branding'] = 'Coastliner'
        with self.assertNumQueries(13):
            # initial['operator'] = self.bova.id
            initial['reg'] = ''
            response = self.client.post(url, initial)
        self.assertIsNone(response.context['form'])

        # check vehicle operator has been changed
        # self.assertContains(response, '/operators/bova-and-over')
        # self.assertContains(response, 'Changed operator from Lynx to Bova and Over')
        self.assertContains(response, 'Changed depot from Long Sutton')
        self.assertContains(response, '<p>I’ll update the other details shortly</p>')

        response = self.client.get('/vehicles/history')
        # self.assertContains(response, 'operator')
        # self.assertContains(response, 'LYNX')
        # self.assertContains(response, 'BOVA')

        # revision = response.context['revisions'][0]
        # self.assertEqual(revision.from_operator, self.lynx)
        # self.assertEqual(revision.to_operator, self.bova)
        # self.assertEqual(str(revision), 'operator: Lynx → Bova and Over, depot: Long Sutton → ')

        response = self.client.get(f'{self.vehicle_2.get_absolute_url()}/history')
        # self.assertContains(response, 'operator')
        # self.assertContains(response, 'LYNX')
        # self.assertContains(response, 'BOVA')

        with self.assertNumQueries(12):
            response = self.client.get(url)
        self.assertContains(response, 'already')

    def test_remove_fleet_number(self):
        self.client.force_login(self.user)

        url = self.vehicle_1.get_absolute_url() + '/edit'

        with self.assertNumQueries(14):
            self.client.post(url, {
                'fleet_number': '',
                'reg': '',
                'operator': self.lynx.id,
            })

        revision = VehicleRevision.objects.get()
        self.assertEqual(str(revision), 'depot: Holt → , notes: Trent Barton → ')

        edit = VehicleEdit.objects.get()

        with self.assertNumQueries(15):
            self.client.post('/admin/vehicles/vehicleedit/', {
                'action': 'apply_edits',
                '_selected_action': edit.id
            })

        edit.refresh_from_db()
        self.assertIsNone(edit.approved)

        vehicle = Vehicle.objects.get(id=self.vehicle_1.id)
        self.assertIsNone(vehicle.fleet_number)
        self.assertEqual('', vehicle.fleet_code)
        self.assertEqual('', vehicle.reg)

        # test user view
        response = self.client.get(self.user.get_absolute_url())
        self.assertContains(response, '1 other edit,')
        self.assertContains(response, 'Trent Barton')

    def test_vehicles_edit(self):
        self.client.force_login(self.user)

        with self.assertNumQueries(10):
            response = self.client.post('/operators/lynx/vehicles/edit')
        self.assertContains(response, 'Select vehicles to update')
        self.assertFalse(VehicleEdit.objects.all())

        with self.assertNumQueries(12):
            response = self.client.post('/operators/lynx/vehicles/edit', {
                'vehicle': self.vehicle_1.id,
                'operator': self.lynx.id,
                'notes': 'foo'
            })
        self.assertContains(response, 'I’ll update those details (1 vehicle) shortly')
        edit = VehicleEdit.objects.get()
        self.assertEqual(edit.vehicle_type, '')
        # self.assertEqual(edit.notes, 'foo')

        self.assertContains(response, 'FD54\xa0JYA')

        # # just updating operator should not create a VehicleEdit, but update the vehicle immediately
        # with self.assertNumQueries(15):
        #     response = self.client.post('/operators/lynx/vehicles/edit', {
        #         'vehicle': self.vehicle_1.id,
        #         'operator': self.bova.id,
        #     })
        # self.assertNotContains(response, 'FD54\xa0JYA')
        # self.vehicle_1.refresh_from_db()
        # self.assertEqual(self.bova, self.vehicle_1.operator)
        # self.assertContains(response, '1 vehicle updated')
        # self.assertEqual(1, VehicleEdit.objects.count())

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

    def test_journey_debug(self):
        with self.assertNumQueries(1):
            response = self.client.get(f'/journeys/{self.journey.id}/debug')
        self.assertEqual({}, response.json())

    def test_service_vehicle_history(self):
        with self.assertNumQueries(5):
            response = self.client.get('/services/spixworth-hunworth-happisburgh/vehicles?date=poop')
        self.assertContains(response, 'Vehicles')
        self.assertContains(response, '/vehicles/')
        self.assertContains(response, '<option selected value="2020-10-20">Tuesday 20 October 2020</option>')
        self.assertContains(response, '1 - FD54\xa0JYA')

        with self.assertNumQueries(5):
            response = self.client.get('/services/spixworth-hunworth-happisburgh/vehicles?date=2004-04-04')
        self.assertNotContains(response, '1 - FD54\xa0JYA')

    def test_api(self):
        with self.assertNumQueries(2):
            response = self.client.get('/api/vehicles/')
        self.assertEqual(
            response.json(),
            {'count': 2, 'next': None, 'previous': None, 'results': [
                {'id': self.vehicle_1.id,
                    'operator': {'id': 'LYNX', 'name': 'Lynx', 'parent': 'Madrigal Electromotive'},
                    'livery': {'id': None, 'name': None, 'left': '#FF0000', 'right': '#FF0000'},
                    'fleet_number': 1, 'fleet_code': '1', 'reg': 'FD54JYA', 'name': '',
                    'branding': '', 'notes': 'Trent Barton', 'withdrawn': False, 'data': {'Depot': 'Holt'},
                    'vehicle_type': {
                        'id': self.vehicle_1.vehicle_type_id,
                        'name': 'Optare Tempo', 'double_decker': False, 'coach': False, 'electric': None},
                    'garage': None},
                {'id': self.vehicle_2.id,
                    'operator': {'id': 'LYNX', 'name': 'Lynx', 'parent': 'Madrigal Electromotive'},
                    'livery': {'id': self.vehicle_2.livery_id, 'name': '',
                               'left': 'linear-gradient(to right,#FF0000 50%,#0000FF 50%)',
                               'right': 'linear-gradient(to left,#FF0000 50%,#0000FF 50%)'},
                    'fleet_number': 50, 'fleet_code': '50', 'reg': 'UWW2X', 'name': '', 'branding': '', 'notes': '',
                    'withdrawn': False, 'data': {'Depot': 'Long Sutton'},
                    'vehicle_type': {
                        'id': self.vehicle_2.vehicle_type_id,
                        'name': 'Optare Spectra', 'double_decker': True, 'coach': False, 'electric': None},
                    'garage': None}
            ]}
        )

        with self.assertNumQueries(1):
            response = self.client.get('/api/vehicles/?reg=sa60twp')
        self.assertEqual(0, response.json()['count'])

        with self.assertNumQueries(2):
            response = self.client.get('/api/vehicles/?search=fd54jya')
        self.assertEqual(1, response.json()['count'])

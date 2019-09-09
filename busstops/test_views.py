# coding=utf-8
import os
import json
import vcr
from django.test import TestCase
from django.core import mail
from django.contrib.gis.geos import Point
from django.shortcuts import render
from .models import Region, AdminArea, District, Locality, StopPoint, StopUsage, Operator, Service, Note


DIR = os.path.dirname(os.path.abspath(__file__))


class ContactTests(TestCase):
    """Tests for the contact form and view"""

    def test_contact_get(self):
        response = self.client.get('/contact')
        self.assertEqual(response.status_code, 200)

    def test_empty_contact_post(self):
        response = self.client.post('/contact')
        self.assertFalse(response.context['form'].is_valid())

    def test_contact_post(self):
        with vcr.use_cassette(os.path.join(DIR, '..', 'data', 'vcr', 'akismet.yaml')):
            response = self.client.post('/contact', {
                'name': 'Rufus "Red" Herring',
                'email': 'rufus@example.com',
                'message': 'Dear John,\r\n\r\nHow are you?\r\n\r\nAll the best,\r\nRufus',
                'referrer': 'https://www.yahoo.com'
            })
        self.assertContains(response, '<h1>Thank you</h1>', html=True)
        self.assertEqual('Dear John,', mail.outbox[0].subject)
        self.assertEqual('"Rufus "Red" Herring" <contact@bustimes.org>', mail.outbox[0].from_email)
        self.assertEqual(['contact@bustimes.org'], mail.outbox[0].to)

    def test_awin_post(self):
        self.assertEqual(400, self.client.get('/awin-transaction').status_code)
        self.client.post('/awin-transaction', {
            'AwinTransactionPush': json.dumps({
                'transactionId': '244231459',
                'transactionDate': '2016-12-06 18:35:28',
                'transactionAmount': '33.7',
                'commission': '0.67',
                'affiliateId': '242611',
                'merchantId': '2678',
                'groupId': '0',
                'bannerId': '0',
                'clickRef': '',
                'clickThroughTime': '2016-12-06 07:15:24',
                'clickTime': '2016-12-06 07:15:24',
                'url': 'https://bustimes.org.uk/services/swe_33-FLC-_-y10',
                'transactionCurrency': 'GBP',
                'commissionGroups': [
                    {
                        'id': '15250',
                        'name': 'Default Commission',
                        'code': 'DEFAULT',
                        'description': ' You will receive 2% commission '
                    }
                ]
            })
        })
        self.assertEqual('💷 67p on a £33.70 transaction', mail.outbox[0].subject)
        self.assertEqual('🚌⏰🤖 <robot@bustimes.org>', mail.outbox[0].from_email)


class ViewsTests(TestCase):
    """Boring tests for various views"""

    @classmethod
    def setUpTestData(cls):
        cls.north = Region.objects.create(pk='N', name='North')
        cls.norfolk = AdminArea.objects.create(
            id=91, atco_code=91, region=cls.north, name='Norfolk'
        )
        cls.north_norfolk = District.objects.create(
            id=91, admin_area=cls.norfolk, name='North Norfolk'
        )
        cls.melton_constable = Locality.objects.create(
            id='E0048689', admin_area=cls.norfolk, name='Melton Constable', latlong=Point(-0.14, 51.51)
        )
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
        StopUsage.objects.create(service=cls.inactive_service, stop=cls.stop, order=0)
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

        cls.chariots = Operator.objects.create(
            pk='AINS',
            name='Ainsley\'s Chariots',
            vehicle_mode='airline',
            region_id='N',
            address='10 King Road\nIpswich',
            phone='0800 1111',
            email='ainsley@example.com',
            url='http://www.ouibus.com',
            twitter='dril\ncoldwarsteve'
        )
        cls.nuventure = Operator.objects.create(pk='VENT', name='Nu-Venture', vehicle_mode='bus', region_id='N')
        cls.service.operator.add(cls.chariots)
        cls.inactive_service.operator.add(cls.chariots)

        cls.note = Note.objects.create(
            text='Mind your head'
        )
        cls.note.operators.set((cls.chariots,))

    def test_index(self):
        """Home page works and doesn't contain a breadcrumb"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Home')

    def test_offline(self):
        """Offline page (for service workers) exists"""
        response = self.client.get('/offline')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, ', it seems like you’re not connected to the Internet')

    def test_not_found(self):
        """Not found responses have a 404 status code"""
        response = self.client.get('/fff')
        self.assertEqual(response.status_code, 404)

    def test_static(self):
        for route in ('/cookies', '/data', '/map'):
            response = self.client.get(route)
            self.assertEqual(response.status_code, 200)

    def test_region(self):
        response = self.client.get('/regions/N')
        self.assertContains(response, 'North')
        self.assertContains(response, '<h1>North</h1>')

        self.assertContains(response, 'Chariots')  # An operator with a current service should be listed
        self.assertNotContains(response, 'Nu-Venture')  # An operator with no current services should not be listed

        self.assertNotContains(response, '<a href="/areas/91">Norfolk</a>')
        self.assertNotContains(response, '<a href="/districts/91">North Norfolk</a>')

        self.melton_constable.district = self.north_norfolk
        self.melton_constable.save()
        response = self.client.get('/regions/N')
        self.assertNotContains(response, '<a href="/areas/91">Norfolk</a>')  # Only one area in this region - so...
        self.assertContains(response, '<a href="/districts/91">North Norfolk</a>')  # ...list the districts in the area

    def test_lowercase_region(self):
        response = self.client.get('/regions/n')
        self.assertContains(
            response, '<link rel="canonical" href="https://bustimes.org/regions/N" />'
        )
        self.assertEqual(response.status_code, 200)

    def test_search(self):
        response = self.client.get('/search?q=melton')
        self.assertContains(response, '1 result found for')
        self.assertContains(response, 'Melton Constable')
        self.assertContains(response, '/localities/melton-constable')

        # CustomSearchForm.is_valid
        response = self.client.get('/search')
        self.assertNotContains(response, 'found for')

        # CustomSearchForm.cleaned_data.get
        response = self.client.get('/search?q=')
        self.assertNotContains(response, 'found for')

        response = render(None, 'search/search.html', {
            'query': True,
            'suggestion': 'bordeaux'
        })
        self.assertContains(response, '<p>Did you mean <a href="/search?q=bordeaux">bordeaux</a>?</p>')

    def test_postcode(self):
        with vcr.use_cassette(os.path.join(DIR, '..', 'data', 'vcr', 'postcode.yaml')):
            # postcode sufficiently near to fake locality
            response = self.client.get('/search?q=w1a 1aa')
            self.assertContains(response, 'Melton Constable')
            self.assertContains(response, '/localities/melton-constable')
            self.assertNotContains(response, 'results found for')

            # postcode looks valid but doesn't exist
            response = self.client.get('/search?q=w1a 1aj')
            self.assertContains(response, '0 results found for')

    def test_admin_area(self):
        """Admin area containing just one child should redirect to that child"""
        StopUsage.objects.create(service=self.service, stop=self.stop, order=0)
        response = self.client.get('/areas/91')
        self.assertRedirects(response, '/localities/melton-constable')

    def test_district(self):
        """Admin area containing just one child should redirect to that child"""
        response = self.client.get('/districts/91')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ga('set', 'dimension1', 'N');")

    def test_locality(self):
        StopUsage.objects.create(service=self.service, stop=self.stop, order=0)
        response = self.client.get('/localities/e0048689')
        self.assertContains(response, '<h1>Melton Constable</h1>')
        self.assertContains(response, '/localities/melton-constable')
        self.assertContains(response, "ga('set', 'dimension1', 'N');")

    def test_stops(self):
        response = self.client.get('/stops.json')
        self.assertEqual(response.status_code, 400)

        response = self.client.get('/stops.json', {
            'ymax': '52.9',
            'xmax': '1.1',
            'ymin': '52.8',
            'xmin': '1.0',
        })
        self.assertEqual('FeatureCollection', response.json()['type'])
        self.assertIn('features', response.json())

    def test_stop(self):
        response = self.client.get('/stops/2900M114')
        self.assertFalse(response.context_data['departures'])
        self.assertContains(response, 'North')
        self.assertContains(response, 'Norfolk')
        self.assertContains(response, 'Melton Constable, opposite Bus Shelter')

    def test_stop_json(self):
        response = self.client.get('/stops/2900M114.json')
        data = response.json()
        self.assertTrue(data['active'])
        self.assertEqual(data['admin_area'], 91)
        self.assertEqual(data['atco_code'], '2900M114')
        self.assertEqual(data['latlong'], [52.8566019427, 1.0331935468])
        self.assertIsNone(data['heading'])
        self.assertIsNone(data['stop_area'])

    def test_inactive_stop(self):
        response = self.client.get('/stops/2900M115')
        self.assertContains(response, 'Sorry, it looks like no services currently stop at', status_code=404)

    def test_operator_found(self):
        """The normal and Accelerated Mobile pages versions should be mostly the same
        (but slightly different)
        """
        for url in ('/operators/ains', '/operators/ainsleys-chariots', '/operators/AINS?amp'):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'An airline operator in')
            self.assertContains(response, 'Contact Ainsley&#39;s Chariots')
            self.assertContains(response, '10 King Road<br />Ipswich', html=True)
            self.assertContains(response, '&#109;&#97;&#105;&#108;&#116;&#111;&#58;&#97;&#105;' +
                                '&#110;&#115;&#108;&#101;&#121;&#64;&#101;&#120;&#97;&#109;' +
                                '&#112;&#108;&#101;&#46;&#99;&#111;&#109;')
            self.assertContains(response, 'http://www.ouibus.com')
            self.assertContains(response, '@dril on Twitter')
            self.assertContains(response, 'Mind your head')  # Note

        self.assertContains(response, '<style amp-custom>')

    def test_operator_not_found(self):
        """An operator with no services, or that doesn't exist, should should return a 404 response"""
        with self.assertNumQueries(4):
            response = self.client.get('/operators/VENT')
            self.assertContains(response, 'Page not found', status_code=404)

        with self.assertNumQueries(4):
            response = self.client.get('/operators/nu-venture')
            self.assertContains(response, 'Page not found', status_code=404)

        with self.assertNumQueries(3):
            response = self.client.get('/operators/poop')
            self.assertEqual(response.status_code, 404)

        with self.assertNumQueries(1):
            response = self.client.get('/operators/POOP')
            self.assertEqual(response.status_code, 404)

    def test_service(self):
        response = self.client.get(self.service.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ouibus')
        self.assertContains(response, '@dril on Twitter')
        self.assertContains(response, 'twitter.com/dril"')
        self.assertContains(response, 'Mind your head')  # Note
        self.assertEqual(self.note.get_absolute_url(), '/operators/ainsleys-chariots')

    def test_national_express_service(self):
        self.chariots.name = 'Hotel Hoppa'
        self.chariots.url = 'http://nationalexpress.com'
        self.chariots.save()

        response = self.client.get(self.service.get_absolute_url())
        self.assertEqual(response.context_data['links'][0], {
            'text': 'Buy tickets on the National Express website',
            'url': 'https://clkuk.pvnsolutions.com/brand/contactsnetwork/click?p=230590&a=3022528&g=24233768'
        })

        self.chariots.name = 'National Express Airport'
        self.assertEqual(self.chariots.get_national_express_url()[-10:], 'g=24233764')

        self.chariots.name = 'National Express Shuttle'
        self.assertEqual(self.chariots.get_national_express_url()[-10:], 'g=21039402')

        response = self.client.get(self.chariots.get_absolute_url())
        self.assertContains(
            response,
            'https://clkuk.pvnsolutions.com/brand/contactsnetwork/click?p=230590&amp;a=3022528&amp;g=21039402'
        )

    def test_service_redirect(self):
        """An inactive service should redirect to a current service with the same description"""
        response = self.client.get('/services/45B')
        self.assertEqual(response.status_code, 301)

    def test_service_not_found(self):
        """An inactive service with no replacement should show a clever 404 page"""
        response = self.client.get('/services/45A')
        self.assertEqual(response.status_code, 404)
        self.assertContains(
            response,
            'Sorry, it looks like the  service <strong>45A</strong> no longer exists.\n    It might have',
            status_code=404
        )
        self.assertContains(response, 'Services operated by Ainsley', status_code=404)
        self.assertContains(response, '<li><a href="/localities/melton-constable">Melton Constable</a></li>',
                            status_code=404)

    def test_service_xml(self):
        """I can view the TransXChange XML for a service"""
        response = self.client.get('/services/ea_21-45-A-y08.xml')
        self.assertEqual(response['Content-Type'], 'text/plain')
        self.assertEqual(response.status_code, 200)

    def test_modes(self):
        """A list of transport modes is turned into English"""
        self.assertContains(render(None, 'modes.html', {
            'modes': ['bus'],
            'noun': 'services'
        }), 'Bus services')
        self.assertContains(render(None, 'modes.html', {
            'noun': 'services'
        }), 'Services')
        self.assertContains(render(None, 'modes.html', {
            'modes': ['bus', 'coach'],
            'noun': 'services'
        }), 'Bus and coach services')
        self.assertContains(render(None, 'modes.html', {
            'modes': ['bus', 'coach', 'tram'],
            'noun': 'services'
        }), 'Bus, coach and tram services')
        self.assertContains(render(None, 'modes.html', {
            'modes': ['bus', 'coach', 'tram', 'cable car'],
            'noun': 'operators'
        }), 'Bus, coach, tram and cable car operators')

    def test_sitemap_index(self):
        response = self.client.get('/sitemap.xml')
        self.assertContains(response, 'https://example.com/sitemap-operators.xml')
        self.assertContains(response, 'https://example.com/sitemap-services.xml')

    def test_sitemap_operators(self):
        response = self.client.get('/sitemap-operators.xml')
        self.assertContains(response, '<url><loc>https://example.com/operators/ainsleys-chariots</loc></url>')

    def test_sitemap_services(self):
        response = self.client.get('/sitemap-services.xml')
        self.assertContains(response, 'https://example.com/services/45a-holt-norwich')

    def test_journey(self):
        """Journey planner"""
        with self.assertNumQueries(0):
            response = self.client.get('/journey')

        with self.assertNumQueries(3):
            response = self.client.get('/journey?from_q=melton')
        self.assertContains(response, 'melton-constable')

        with self.assertNumQueries(3):
            response = self.client.get('/journey?to_q=melton')
        self.assertContains(response, 'melton-constable')

        with self.assertNumQueries(7):
            response = self.client.get('/journey?from_q=melton&to_q=constable')

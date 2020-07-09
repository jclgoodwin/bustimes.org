import os
from vcr import use_cassette
from django.test import TestCase, override_settings
from django.core.cache import cache
from django.conf import settings
from django.core.management import call_command
from busstops.models import Region, Operator, Service, DataSource
from .models import Situation


class SiriSXTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        region = Region.objects.create(id='NW', name='North West')
        operator = Operator.objects.create(region=region, id='HATT', name='Hattons of Huyton')
        service = Service.objects.create(line_name='156', service_code='156', date='2020-01-01', current=True)
        service.operator.add(operator)
        DataSource.objects.create(name='Transport for the North', settings={'app_id': '', 'app_key': ''})
        DataSource.objects.create(name='Arriva')

    def test_get(self):
        self.assertFalse(self.client.get('/siri').content)

    @override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
    def test_subscribe_and_hearbeat(self):
        self.assertIsNone(cache.get('Heartbeat:HAConTest'))
        self.assertIsNone(cache.get('Heartbeat:TransportAPI'))

        cassette = os.path.join(settings.DATA_DIR, 'vcr', 'siri_sx.yaml')

        with use_cassette(cassette, match_on=['body']):
            with self.assertRaises(ValueError):
                call_command('subscribe', 'tfn')
            with self.assertRaises(ValueError):
                call_command('subscribe', 'arriva')

        response = self.client.post('/siri', """<?xml version="1.0" ?>
<Siri xmlns:ns1="http://www.siri.org.uk/siri" xmlns="http://www.siri.org.uk/siri" version="1.3">
  <HeartbeatNotification>
    <RequestTimestamp>2020-06-21T12:25:05+01:00</RequestTimestamp>
    <ProducerRef>HAConTest</ProducerRef>
    <MessageIdentifier>HAConToBusTimesET</MessageIdentifier>
    <ValidUntil>2020-06-22T02:25:02+01:00</ValidUntil>
    <ShortestPossibleCycle>PT10S</ShortestPossibleCycle>
    <ServiceStartedTime>2020-06-21T02:17:36+01:00</ServiceStartedTime>
  </HeartbeatNotification>
</Siri>""", content_type='text/xml')
        self.assertTrue(response.content)
        self.assertTrue(cache.get('Heartbeat:HAConTest'))

        cache.set('Heartbeat:TransportAPI', True)
        with use_cassette(cassette, match_on=['body']):
            call_command('subscribe', 'tfn')
            call_command('subscribe', 'arriva')

    def test_siri_sx(self):
        with use_cassette(os.path.join(settings.DATA_DIR, 'vcr', 'siri_sx.yaml'), match_on=['body']):
            with self.assertNumQueries(75):
                call_command('import_siri_sx', 'hen hom', 'roger poultry')
        with use_cassette(os.path.join(settings.DATA_DIR, 'vcr', 'siri_sx.yaml'), match_on=['body']):
            with self.assertNumQueries(11):
                call_command('import_siri_sx', 'hen hom', 'roger poultry')

        situation = Situation.objects.first()

        self.assertEqual(situation.situation_number, 'RGlzcnVwdGlvbk5vZGU6MTA3NjM=')
        self.assertEqual(situation.reason, 'roadworks')
        self.assertEqual(situation.summary, 'East Didsbury bus service changes Monday 11th May until Thursday 14th \
May. ')
        self.assertEqual(situation.text, 'Due to resurfacing works there will be bus service diversions and bus stop \
closures from Monday 11th May until Thursday 14th may. ')
        self.assertEqual(situation.reason, 'roadworks')

        response = self.client.get(situation.get_absolute_url())
        self.assertContains(response, '2020-05-10T23:01:00Z')

        consequence = situation.consequence_set.get()
        self.assertEqual(consequence.text, """Towards East Didsbury terminus customers should alight opposite East \
Didsbury Rail Station as this will be the last stop. From here its a short walk to the terminus. \n
Towards Manchester the 142 service will begin outside Didsbury Cricket club . """)

        with self.assertNumQueries(10):
            response = self.client.get('/services/156')

        self.assertContains(response, "<p>East Lancashire Road will be subjected to restrictions, at Liverpool Road,\
 from Monday 17 February 2020 for approximately 7 months.</p>")
        self.assertContains(response, "<p>Route 156 will travel as normal from St Helens to Haydock Lane, then u-turn \
at Moore Park Way roundabout, Haydock Lane, Millfield Lane, Tithebarn Road, then as normal route to Garswood (omitting \
East Lancashire Road and Liverpool Road).</p>""")

        self.assertContains(response, '<a href="https://www.merseytravel.gov.uk/travel-updates/east-lancashire-road-(haydock)/" \
rel="nofollow">www.merseytravel.gov.uk/travel-updates/east-lancashire-road-(haydock)</a>')

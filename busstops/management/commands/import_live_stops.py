"""
Add the relevant live source to stop points if departure boards are available from each that source

Usage:

    ./manage.py import_live_stops
"""

import requests
from bs4 import BeautifulSoup
from time import sleep
from django.core.management.base import BaseCommand
from busstops.models import StopPoint, LiveSource


kent = LiveSource.objects.get_or_create(name='Kent')[0]
yorkshire = LiveSource.objects.get_or_create(name='Y')[0]
travelwest = LiveSource.objects.get_or_create(name='west')[0]
ayrshire = LiveSource.objects.get_or_create(name='ayr')[0]
buckinghamshire = LiveSource.objects.get_or_create(name='buck')[0]
cambridgeshire = LiveSource.objects.get_or_create(name='camb')[0]



class Command(BaseCommand):

    @staticmethod
    def maybe_add_acislive_source(stop, live_source, prefix):
        url = 'http://%s.acislive.com/pip/stop_simulator.asp' % prefix
        request = requests.get(
            url,
            {'naptan': stop.naptan_code}
        )
        print request.url
        soup = BeautifulSoup(request.text, 'html.parser')
        if soup.title and soup.title.text != 'Sorry':
            stop.live_sources.add(live_source)
            print soup.title
        else:
            print soup.title
        print '\n'
        sleep(1)

    @staticmethod
    def maybe_add_acisconnect_source(stop, live_source, prefix):
        print stop.get_absolute_url()
        url = 'http://%s.acisconnect.com/Text/WebDisplay.aspx' % prefix
        request = requests.get(
            url,
            {'stopRef': stop.pk}
        )
        soup = BeautifulSoup(request.text, 'html.parser')
        text = soup.find(id='UpdatePanel1').text
        if 'System unavailable' not in text:
            stop.live_sources.add(live_source)
        else:
            print text
        sleep(1)

    def handle(self, *args, **options):

        print 'cambridgeshire'
        for stop in StopPoint.objects.filter(admin_area__id=71, live_sources=None).exclude(service=None):
            self.maybe_add_acisconnect_source(stop, cambridgeshire, 'cambridgeshire')

        print 'buckinghamshire'
        for stop in StopPoint.objects.filter(admin_area__id=70, live_sources=None).exclude(service=None):
            self.maybe_add_acisconnect_source(stop, buckinghamshire, 'buckinghamshire')

        print 'ayrshire'
        for stop in StopPoint.objects.filter(admin_area__id__in=(138, 132, 120), live_sources=None).exclude(service=None):
            self.maybe_add_acisconnect_source(stop, ayrshire, 'ayrshire')

        print 'west'
        for stop in StopPoint.objects.filter(admin_area__id__in=(1, 9), live_sources=None).exclude(service=None):
            self.maybe_add_acisconnect_source(stop, travelwest, 'travelwest')

        return

        print 'kent'
        stops = StopPoint.objects.filter(pk__startswith='240', live_sources=None).exclude(service=None)
        for stop in stops:
            self.maybe_add_live_source(stop, kent, 'kent')

        print 'yorkshire'
        stops = StopPoint.objects.filter(admin_area__region__name='Yorkshire', live_sources=None).exclude(service=None)
        for stop in stops:
            self.maybe_add_live_source(stop, yorkshire, 'tsy')

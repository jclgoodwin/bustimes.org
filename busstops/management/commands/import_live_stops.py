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


class Command(BaseCommand):

    @staticmethod
    def maybe_add_live_source(stop, live_source, prefix):
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

    def handle(self, *args, **options):

        print 'kent'
        stops = StopPoint.objects.filter(pk__startswith='240', live_sources=None).exclude(service=None)
        for stop in stops:
            self.maybe_add_live_source(stop, kent, 'kent')

        print 'yorkshire'
        stops = StopPoint.objects.filter(admin_area__region__name='Yorkshire', live_sources=None).exclude(service=None)
        for stop in stops:
            self.maybe_add_live_source(stop, yorkshire, 'tsy')

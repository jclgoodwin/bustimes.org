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


yorkshire = LiveSource.objects.get_or_create(name='Y')[0]


class Command(BaseCommand):

    def handle(self, *args, **options):
        for stop in StopPoint.objects.filter(admin_area__region__name='Yorkshire', live_sources=None).exclude(service=None)[:100]:
            url = 'http://tsy.acislive.com/pip/stop_simulator.asp'
            request = requests.get(
                url,
                {'naptan': stop.naptan_code},
            )
            request.url
            soup = BeautifulSoup(request.text, 'html.parser')
            print soup.title
            print stop.get_absolute_url()
            if soup.title and soup.title.text != 'Sorry':
                stop.live_sources.add(yorkshire)
                print 'added'
            print '\n'
            sleep(1)

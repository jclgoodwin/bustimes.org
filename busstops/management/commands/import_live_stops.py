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

    def handle(self, *args, **options):

        # Kent
        print 'kent'
        pks = (
            '2400A070000A', '2400A018790A', '2400A019210A', '240096623', '240096625',
            '2400A018770A', '2400A018870A', '240096627', '240096629', '2400A018850A',
            '2400A018760A', '2400A018880A', '2400A018780A', '2400A018860A', '240096605',
            '240096607', '2400A018810A', '2400A018830A', '240096609', '240096611', '240075087',
            '240075089', '240097375', '2400101288', '240096663', '2400A019920A', '2400A019930A',
            '2400A019660A', '2400A019280A', '2400A060520A', '2400A019330A', '2400A018800A',
            '2400A018840A', '2400102527', '2400A019270A', '2400104629', '240096613', '240096617',
            '240096637', '2400A019260A', '2400A018820A', '2400105652', '2400105654', '2400101264',
            '2400101304', '2400A009020A', '2400A009090A', '2400A018750A', '2400A018890A',
            '2400A019000A', '2400A019010A', '2400A018970A', '2400A018980A', '2400A070010A',
            '2400A070020A', '2400A070030A', '2400A070050A', '2400103084', '2400A018990A',
            '2400103086', '2400104440', '2400A018440A', '2400A018630A', '2400A018420A',
            '2400A018640A', '2400A018430A', '2400A018670A', '2400A018680A', '2400A018690A',
            '2400A018250A', '2400A018410A', '2400A018650A', '2400A018450A', '2400A018620A',
            '2400A018400A', '2400A018660A', '2400104339', '2400100087', '2400100089', '2400100079',
            '2400100081', '2400104344', '2400A009010A', '2400A009110A', '2400A009120A',
            '2400A060760R', '2400A018710A', '2400A018930A', '240096572', '240098186', '2400102525',
            '2400A018720A', '2400A018920A', '240098190', '2400105576', '2400A009140A',
            '2400A018730A', '2400A018910A', '2400A009150A', '2400102521', '2400102523',
            '2400A018740A', '2400A018900A', '2400103082', '2400A018480A', '2400A018600A',
            '2400100072', '2400100074', '2400A018530A', '2400A018540A', '2400A018470A',
            '2400A018610A', '240096639', '2400A018460A', '2400100075', '2400100077',
            '2400A018510A', '2400A018960A', '2400A018570A', '2400A018940A', '2400A018550A',
            '2400A018560A', '2400A018520A', '2400A060750R', '240096641', '2400A018580A',
            '2400A018500A', '2400A018590A'
        )
        stops = StopPoint.objects.filter(pk__in=pks)
        kent.stoppoint_set.set(stops)


        # Yorkshire
        print 'yorkshire'
        stops = StopPoint.objects.filter(admin_area__region__name='Yorkshire', live_sources=None)
        for stop in stops.exclude(service=None):
            url = 'http://tsy.acislive.com/pip/stop_simulator.asp'
            request = requests.get(
                url,
                {'naptan': stop.naptan_code},
            )
            soup = BeautifulSoup(request.text, 'html.parser')
            print soup.title
            print stop.get_absolute_url()
            if soup.title and soup.title.text != 'Sorry':
                stop.live_sources.add(yorkshire)
                print 'added'
            print '\n'
            sleep(1)

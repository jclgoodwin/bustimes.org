"""
Add the relevant live source to stop points if departure boards are available from each that source

Usage:

    ./manage.py import_live_stops
"""

import requests
import json
from bs4 import BeautifulSoup
from time import sleep
from django.core.management.base import BaseCommand
from ...models import StopPoint, LiveSource


kent = LiveSource.objects.get_or_create(name='Kent')[0]
yorkshire = LiveSource.objects.get_or_create(name='Y')[0]
travelwest = LiveSource.objects.get_or_create(name='west')[0]
ayrshire = LiveSource.objects.get_or_create(name='ayr')[0]
buckinghamshire = LiveSource.objects.get_or_create(name='buck')[0]
cambridgeshire = LiveSource.objects.get_or_create(name='camb')[0]
aberdeen = LiveSource.objects.get_or_create(name='aber')[0]
cardiff = LiveSource.objects.get_or_create(name='card')[0]
swindon = LiveSource.objects.get_or_create(name='swin')[0]
metrobus = LiveSource.objects.get_or_create(name='metr')[0]



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

    @staticmethod
    def get_clustered_stops(subdomain):
        url = 'http://%s.acisconnect.com/ConnectService.svc/GetClusteredStops' % subdomain
        params = {
            'topLeft': {'lon': -100, 'lat': 100, 'CLASS_NAME': 'OpenLayers.LonLat'},
            'bottomRight': {'lon': 100, 'lat': -100, 'CLASS_NAME': 'OpenLayers.LonLat'},
            'zoomLevel': 5
        }
        response = requests.post(url, json=params)
        json_string = response.json().get('d').replace('MapStopResponse=', '')
        parsed_json = json.loads(json_string)
        return parsed_json['Stops'] if 'Stops' in parsed_json else parsed_json['AllFoundStops']

    @staticmethod
    def get_stops_for_cluster(subdomain, cluster_id):
        url = 'http://%s.acisconnect.com/ConnectService.svc/GetStopsForCluster' % subdomain
        params = {
            'clusterID': cluster_id
        }
        response = requests.post(url, json=params)
        json_string = response.json().get('d').replace('MapStopResponse=', '')
        parsed_json = json.loads(json_string)
        print response.text
        sleep(1)
        return parsed_json['Stops'] if 'Stops' in parsed_json else parsed_json['AllFoundStops']

    def handle(self, *args, **options):
        for subdomain, livesource in (
            ('cambridgeshire', cambridgeshire),
            ('buckinghamshire', buckinghamshire),
            ('ayrshire', ayrshire),
            ('travelwest', travelwest),
            ('aberdeen', aberdeen),
            ('cardiff', cardiff),
            ('swindon', swindon),
            ('metrobus', metrobus)
        ):
            print subdomain
            stop_ids = []
            for cluster in self.get_clustered_stops(subdomain):
                if cluster['ClusterCount'] == 1:
                    stop_ids.append(cluster['StopRef'])
                else:
                    stop_ids.extend((stop['StopRef'] for stop in self.get_stops_for_cluster(subdomain, cluster['ClusterId'])))
            print stop_ids
            stoppoints = StopPoint.objects.filter(pk__in=stop_ids)
            livesource.stoppoint_set.add(*stoppoints)


"""
Usage:

    ./manage.py import_live_stops
"""

from time import sleep
import json
import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from ...models import StopPoint, LiveSource


DELAY = 1


class Command(BaseCommand):
    """
    Adds the relevant live source to stop points
    if departure boards are available from that source for that stop point
    """
    @staticmethod
    def maybe_add_acislive_source(stop, live_source, prefix):
        url = 'http://%s.acislive.com/pip/stop_simulator.asp' % prefix
        request = requests.get(
            url,
            {'naptan': stop.naptan_code}
        )
        soup = BeautifulSoup(request.text, 'html.parser')
        if soup.title and soup.title.text != 'Sorry':
            stop.live_sources.add(live_source)
        sleep(DELAY)

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
        sleep(DELAY)

    @staticmethod
    def get_cluster_something(subdomain, path, params):
        url = 'http://%s.acisconnect.com/ConnectService.svc/Get%s' % (subdomain, path)
        response = requests.post(url, json=params)
        json_string = response.json().get('d').replace('MapStopResponse=', '')
        parsed_json = json.loads(json_string)
        sleep(DELAY)
        return parsed_json.get('Stops') or parsed_json.get('AllFoundStops')

    @classmethod
    def get_clustered_stops(cls, subdomain):
        return cls.get_cluster_something(subdomain, 'ClusteredStops', {
            'topLeft': {'lon': -100, 'lat': 100, 'CLASS_NAME': 'OpenLayers.LonLat'},
            'bottomRight': {'lon': 100, 'lat': -100, 'CLASS_NAME': 'OpenLayers.LonLat'},
            'zoomLevel': 5
        })

    @classmethod
    def get_stops_for_cluster(cls, subdomain, cluster_id):
        return cls.get_cluster_something(subdomain, 'StopsForCluster', {
            'clusterID': cluster_id
        })

    def handle(self, *args, **options):
        live_sources = {
            # 'kent': LiveSource.objects.get_or_create(name='Kent')[0],
            # 'yorkshire': LiveSource.objects.get_or_create(name='Y')[0],
            'aberdeen': LiveSource.objects.get_or_create(name='aber')[0],
            'ayrshire': LiveSource.objects.get_or_create(name='ayr')[0],
            'buckinghamshire': LiveSource.objects.get_or_create(name='buck')[0],
            'cambridgeshire': LiveSource.objects.get_or_create(name='camb')[0],
            'cardiff': LiveSource.objects.get_or_create(name='card')[0],
            'metrobus': LiveSource.objects.get_or_create(name='metr')[0],
            'swindon': LiveSource.objects.get_or_create(name='swin')[0],
            'travelwest': LiveSource.objects.get_or_create(name='west')[0]
        }

        for subdomain, live_source in live_sources.items():
            print(subdomain)
            stop_ids = []
            for cluster in self.get_clustered_stops(subdomain):
                if cluster['ClusterCount'] == 1:
                    stop_ids.append(cluster['StopRef'])
                else:
                    stop_ids.extend(
                        (stop['StopRef'] for stop in self.get_stops_for_cluster(
                            subdomain, cluster['ClusterId']
                        ))
                    )
            print(stop_ids)
            stoppoints = StopPoint.objects.filter(pk__in=stop_ids)
            live_source.stoppoint_set.add(*stoppoints)

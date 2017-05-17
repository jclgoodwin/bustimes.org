import os
import time
import zipfile
import csv
import requests
# from django.contrib.gis.geos import LineString, MultiLineString
from django.core.management.base import BaseCommand
from django.db import transaction
from ...models import Operator, Service


MODES = {
    '2': 'rail',
    '3': 'bus'
}
COLLECTIONS = (
    'luasbus', 'dublinbus', 'kenneallys', 'locallink', 'irishrail', 'ferries',
    'manda', 'finnegans', 'citylink', 'nitelink', 'buseireann', 'mcgeehan',
    'mkilbride', 'expressbus', 'edmoore', 'collins', 'luas', 'sro',
    'dublincoach', 'burkes', 'mhealy', 'kearns', 'josfoley', 'buggy',
    'jjkavanagh', 'citydirect', 'aircoach', 'matthews', 'wexfordbus',
    'dualway', 'tralee', 'sbloom', 'mcginley', 'swordsexpress', 'suirway',
    'sdoherty', 'pjmartley', 'mortons', 'mgray', 'mcgrath', 'mangan',
    'lallycoach', 'halpenny', 'eurobus', 'donnellys', 'cmadigan', 'bkavanagh',
    'ptkkenneally', 'farragher', 'fedateoranta'
)


def get_rows(csv_file):
    return csv.DictReader(line.decode('utf-8-sig') for line in csv_file)


def write_zip_file(path, response):
    with open(path, 'wb') as zip_file:
        for chunk in response.iter_content(chunk_size=102400):
            zip_file.write(chunk)


class Command(BaseCommand):
    # @staticmethod
    # def add_arguments(parser):
    #     parser.add_argument('filenames', nargs='+', type=str)

    @transaction.atomic
    def handle_zipfile(self, archive_name):
        routes = {}
        trips = {}
        agencies = {}
        with zipfile.ZipFile(archive_name) as archive:
            with archive.open('agency.txt') as csv_file:
                for row in get_rows(csv_file):
                    agencies[row['agency_id']] = row
            with archive.open('routes.txt') as csv_file:
                for row in get_rows(csv_file):
                    routes[row['route_id']] = row
                    routes[row['route_id']]['trips'] = []
            with archive.open('trips.txt') as csv_file:
                for row in get_rows(csv_file):
                    trips[row['trip_id']] = row
                    trips[row['trip_id']]['stop_times'] = []
                    routes[row['route_id']]['trips'].append(row)
            with archive.open('stop_times.txt') as csv_file:
                for row in get_rows(csv_file):
                    trips[row['trip_id']]['stop_times'].append(row)

        for route in routes.values():
            defaults = {
                'region_id': 'LE',
                'line_name': route['route_short_name'],
                'date': '2017-01-01',
            }
            if route['trips']:
                defaults['description'] = route['trips'][0]['trip_headsign']
            else:
                print(route)
                break
            if route['route_type'] in MODES:
                defaults['mode'] = MODES[route['route_type']]
            service = Service.objects.update_or_create(service_code=route['route_id'], defaults=defaults)[0]
            if route['agency_id']:
                if Operator.objects.filter(name=agencies[route['agency_id']]['agency_name']).exists():
                    service.operator.add(Operator.objects.get(name=agencies[route['agency_id']]['agency_name']))
                else:
                    print(agencies[route['agency_id']]['agency_name'])

    def handle(self, *args, **options):
        session = requests.Session()

        for collection in COLLECTIONS:
            path = 'google_transit_{}.zip'.format(collection)
            url = 'http://www.transportforireland.ie/transitData/' + path
            if os.path.exists(path):
                response = session.get(url, headers={
                    'if-modified-since': time.ctime(os.path.getmtime(path) - 3600)
                }, stream=True)
                if response.status_code != 304:
                    write_zip_file(path, response)
            else:
                write_zip_file(path, session.get(url, stream=True))
            self.handle_zipfile(path)

import requests
import gpxpy.gpx
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import GEOSGeometry, MultiLineString
from timetables import txc
from ...models import Service, StopPoint
# from .generate_departures import combine_date_time


class Command(BaseCommand):
    # def get_linestring(self, session, access_token, params, linestring):
    #     coordinates = ';'.join('{},{}'.format(point[0], point[1]) for point in linestring)
    #     url = 'https://api.mapbox.com/matching/v5/mapbox/driving/{}.json'.format(coordinates)
    #     response = session.get(url, params=params)
    #     json = response.json()
    #     if json['matchings']:
    #         return GEOSGeometry(str(json['matchings'][0]['geometry']))

    def handle(self, *args, **options):
        session = requests.Session()
        # access_token = ''
        # params = {
        #     'access_token': access_token,
        #     'geometries': 'geojson',
        #     'overview': 'full'
        # }
        # for service in Service.objects.filter(operator='LYNX', current=True):
        #     print(service)
        #     linestrings = (self.get_linestring(session, access_token, params, ls) for ls in service.geometry)
        #     linestrings = (ls for ls in linestrings if ls)
        #     service.geometry = MultiLineString(*linestrings).simplify()
        #     service.save()

        for service in Service.objects.filter(current=True, operator='SNDR'):
            stopses = set()
            for file in service.get_files_from_zipfile():
                timetable = txc.Timetable(file)
                for grouping in timetable.groupings:
                    for journeypattern in grouping.journeypatterns:
                        stop_ids = [journeypattern.sections[0].timinglinks[0].origin.stop.atco_code]
                        for section in journeypattern.sections:
                            for timinglink in section.timinglinks:
                                stop_ids.append(timinglink.destination.stop.atco_code)
                        stopses.add(','.join(stop_ids))

            stopses = [string.split(',') for string in stopses]

            linestrings = []
            for stop_ids in stopses:
                stops = StopPoint.objects.in_bulk((stop_ids))

                gpx = gpxpy.gpx.GPX()
                gpx_track = gpxpy.gpx.GPXTrack()
                gpx.tracks.append(gpx_track)

                gpx_segment = gpxpy.gpx.GPXTrackSegment()
                gpx_track.segments.append(gpx_segment)

                for stop_id in stop_ids:
                    stop = stops[stop_id]
                    point = gpxpy.gpx.GPXTrackPoint(stop.latlong.y, stop.latlong.x)
                    gpx_segment.points.append(point)

                xml = gpx.to_xml()

                response = session.post('https://bustimes.org/match?type=json&points_encoded=false',
                                        headers={'Content-Type': 'application/gpx+xml'},
                                        data=xml)
                if response.ok:
                    json = response.json()
                    if json['map_matching']['distance']:
                        geometry = json['paths'][0]['points']
                        linestrings.append(GEOSGeometry(str(geometry)))

            service.geometry = MultiLineString(*linestrings)
            service.save()
            print(service.pk)
            # return

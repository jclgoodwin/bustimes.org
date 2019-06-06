from os.path import join
# from datetime import date
# from urllib.parse import urlencode
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import LineString, MultiLineString
from django.conf import settings
# from django.db import transaction
from multigtfs.models import Feed
from ...models import Service, StopUsage, StopPoint
from timetables.gtfs import get_timetable


class Command(BaseCommand):
    def handle(self, *args, **options):
        collection = 'Ensignbus'

        Feed.objects.filter(name=collection).delete()
        feed = Feed.objects.create(name='Ensignbus')
        feed.import_gtfs(join(settings.DATA_DIR, 'original-gtfs'))

        for route in feed.route_set.all():
            service = Service.objects.get(service_code=route.route_id)

            timetable = get_timetable((route,))

            direction = 'Outbound'
            stops = []
            linestrings = []
            for grouping in timetable.groupings:
                points = []
                for i, row in enumerate(grouping.rows):
                    stop_id = row.part.stop.atco_code
                    points.append(StopPoint.objects.get(atco_code=stop_id).latlong)
                    stops.append(
                        StopUsage(
                            service=service,
                            stop_id=stop_id,
                            order=i,
                            direction=direction
                        )
                    )
                direction = 'Inbound'
                linestrings.append(LineString(points))
            StopUsage.objects.bulk_create(stops)
            service.geometry = MultiLineString(linestrings)
            service.save()

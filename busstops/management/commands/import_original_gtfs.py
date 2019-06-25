from os.path import join
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import LineString, MultiLineString
from django.conf import settings
from django.db import transaction
from multigtfs.models import Feed
from ...models import DataSource, Service, ServiceCode, StopPoint, StopUsage
from timetables.gtfs import get_timetable


class Command(BaseCommand):
    @transaction.atomic
    def handle(self, *args, **options):
        collection = 'bustimes.org'
        scheme = f'{collection} GTFS'
        source, _ = DataSource.objects.get_or_create(name=scheme)

        Feed.objects.filter(name=collection).delete()
        feed = Feed.objects.create(name=collection)
        feed.import_gtfs(join(settings.DATA_DIR, 'original-gtfs'))

        for route in feed.route_set.all():
            service = Service.objects.get(service_code=route.route_id)
            service.stopusage_set.all().delete()
            service.servicecode_set.all().delete

            timetable = get_timetable((route,))

            service.source = source

            ServiceCode.objects.get_or_create(scheme=scheme, code=route.route_id, service=service)

            direction = 'Outbound'
            stops = []
            linestrings = []
            for grouping in timetable.groupings:
                points = []
                for i, row in enumerate(grouping.rows):
                    stop_id = row.part.stop.atco_code
                    try:
                        points.append(StopPoint.objects.get(atco_code=stop_id).latlong)
                        stops.append(
                            StopUsage(
                                service=service,
                                stop_id=stop_id,
                                order=i,
                                direction=direction
                            )
                        )
                    except StopPoint.DoesNotExist:
                        pass
                direction = 'Inbound'
                if len(points) > 1:
                    linestrings.append(LineString(points))
            StopUsage.objects.bulk_create(stops)
            if linestrings:
                service.geometry = MultiLineString(linestrings)
                service.save()

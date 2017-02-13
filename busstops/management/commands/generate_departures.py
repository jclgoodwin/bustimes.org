from datetime import date
from django.core.management.base import BaseCommand
from django.db import transaction
from txc import txc
from ...models import Service, Journey, StopUsageUsage, StopPoint
from ...utils import get_files_from_zipfile


def handle_timetable(service, timetable):
    for grouping in timetable.groupings:
        stops = {row.part.stop.atco_code for row in grouping.rows}
        existent_stops = StopPoint.objects.filter(atco_code__in=stops).values_list('atco_code', flat=True)
        for vj in grouping.journeys:
            stopusageusages = []
            journey = Journey(service=service, datetime='{} {}'.format(timetable.date, vj.departure_time))
            for i, (su, time) in enumerate(vj.get_times()):
                if su.stop.atco_code in existent_stops:
                    if not su.activity or su.activity.startswith('pickUp'):
                        stopusageusages.append(
                            StopUsageUsage(datetime='{} {}'.format(timetable.date, time),
                                           order=i, stop_id=su.stop.atco_code)
                        )
                    journey.destination_id = su.stop.atco_code
            if journey.destination_id:
                journey.save()
                for suu in stopusageusages:
                    suu.journey = journey
                StopUsageUsage.objects.bulk_create(stopusageusages)


class Command(BaseCommand):
    @transaction.atomic
    def handle(self, *args, **options):
        Journey.objects.all().delete()

        print(Journey.objects.all())
        print(StopUsageUsage.objects.all())

        day = date.today()
        for service in Service.objects.filter(current=True):
            print(service)
            for xml_file in get_files_from_zipfile(service):
                timetable = txc.Timetable(xml_file, day)
                if not hasattr(timetable, 'groupings'):
                    continue
                handle_timetable(service, timetable)

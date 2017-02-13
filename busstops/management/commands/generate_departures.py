from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from txc import txc
from ...models import Service, Journey, StopUsageUsage, StopPoint
from ...utils import get_files_from_zipfile


ONE_DAY = timedelta(days=1)


def handle_timetable(service, timetable, day):
    if day.weekday() not in timetable.operating_profile.regular_days:
        return
    if not timetable.operating_period.contains(day):
        return
    # if not hasattr(timetable, 'groupings'):
        # return
    for grouping in timetable.groupings:
        stops = {row.part.stop.atco_code for row in grouping.rows}
        existent_stops = StopPoint.objects.filter(atco_code__in=stops).values_list('atco_code', flat=True)
        for vj in grouping.journeys:
            if not vj.should_show(day):
                continue
            date = day
            previous_time = None
            stopusageusages = []
            journey = Journey(service=service, datetime='{} {}'.format(date, vj.departure_time))
            for i, (su, time) in enumerate(vj.get_times()):
                if previous_time and previous_time > time:
                    date += ONE_DAY
                if su.stop.atco_code in existent_stops:
                    if not su.activity or su.activity.startswith('pickUp'):
                        stopusageusages.append(
                            StopUsageUsage(datetime='{} {}'.format(date, time),
                                           order=i, stop_id=su.stop.atco_code)
                        )
                    journey.destination_id = su.stop.atco_code
                previous_time = time
            if journey.destination_id:
                journey.save()
                for suu in stopusageusages:
                    suu.journey = journey
                StopUsageUsage.objects.bulk_create(stopusageusages)


class Command(BaseCommand):
    @transaction.atomic
    def handle(self, *args, **options):
        Journey.objects.all().delete()

        day = date.today()
        for service in Service.objects.filter(current=True,
                                              region__in=('EA',)).exclude(region__in=('L', 'Y', 'NI')):
            print(service)
            for i, xml_file in enumerate(get_files_from_zipfile(service)):
                timetable = txc.Timetable(xml_file, None)
                handle_timetable(service, timetable, day)
                j = 1
                while j < 7:
                    handle_timetable(service, timetable, day + ONE_DAY * j)
                    j += 1

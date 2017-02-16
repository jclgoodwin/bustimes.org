from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from txc import txc
from ...models import Region, Service, Journey, StopUsageUsage, StopPoint
from ...utils import get_files_from_zipfile


ONE_DAY = timedelta(days=1)


def handle_timetable(service, timetable, day):
    if hasattr(timetable, 'operating_profile') and day.weekday() not in timetable.operating_profile.regular_days:
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


@transaction.atomic
def handle_region(region):
    today = date.today()
    NEXT_WEEK = today + ONE_DAY * 7
    # delete journeys before today
    print('deleting journeys before', today)
    print(Journey.objects.filter(service__region=region, datetime__date__lt=today).delete())
    # get the date of the last generated journey
    last_journey = Journey.objects.filter(service__region=region).order_by('datetime').last()
    if last_journey:
        today = last_journey.datetime.date() + ONE_DAY
        if today > NEXT_WEEK:
            return

    for service in Service.objects.filter(region=region, current=True):
        # print(service)
        for i, xml_file in enumerate(get_files_from_zipfile(service)):
            timetable = txc.Timetable(xml_file, None)
            day = today
            while day <= NEXT_WEEK:
                # print('generating departures for', day)
                handle_timetable(service, timetable, day)
                day += ONE_DAY


class Command(BaseCommand):
    def handle(self, *args, **options):
        for region in Region.objects.all().exclude(id__in=('L', 'Y', 'NI')):
            print(region)
            handle_region(region)

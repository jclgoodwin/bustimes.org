import os
from multiprocessing import Pool
from datetime import timedelta, datetime
from pytz.exceptions import NonExistentTimeError
from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings
from django.utils import timezone
from txc import txc, ni
from ...models import Region, Service, Journey, StopUsageUsage, StopPoint
from ...utils import get_files_from_zipfile


ONE_DAY = timedelta(days=1)


def combine_date_time(date, time):
    combo = datetime.combine(date, time)
    try:
        return timezone.make_aware(combo)
    except NonExistentTimeError as e:
        return timezone.make_aware(combo + timedelta(hours=1))


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
            journey = Journey(service=service, datetime=combine_date_time(date, vj.departure_time))
            for i, (su, time) in enumerate(vj.get_times()):
                if previous_time and previous_time > time:
                    date += ONE_DAY
                if su.stop.atco_code in existent_stops:
                    if not su.activity or su.activity.startswith('pickUp'):
                        stopusageusages.append(
                            StopUsageUsage(datetime=combine_date_time(date, time),
                                           order=i, stop_id=su.stop.atco_code)
                        )
                    journey.destination_id = su.stop.atco_code
                previous_time = time
            if journey.destination_id:
                journey.save()
                for suu in stopusageusages:
                    suu.journey = journey
                StopUsageUsage.objects.bulk_create(stopusageusages)


def do_ni_service(service, groupings, day):
    previous_time = None
    for grouping in groupings:
        for journey in grouping['Journeys']:
            if not ni.should_show(journey, day):
                continue

            stopusageusages = []
            for i, su in enumerate(journey['StopUsages']):
                if su['Location'][0] != '7':
                    print(service, su)
                    continue
                destination = su['Location']
                if su['Departure']:
                    departure = datetime.strptime(su['Departure'], '%H:%M').time()
                    if su['Activity'] != 'S':
                        if previous_time and departure < previous_time:
                            day += ONE_DAY
                        stopusageusages.append(
                            StopUsageUsage(datetime=combine_date_time(day, departure),
                                           order=i, stop_id=su['Location'])
                        )
                else:
                    departure = None
                previous_time = departure
            departure = stopusageusages[0].datetime
            journey = Journey(service=service, datetime=departure, destination_id=destination)
            journey.save()
            for suu in stopusageusages:
                suu.journey = journey
            StopUsageUsage.objects.bulk_create(stopusageusages)


@transaction.atomic
def handle_region(region):
    print(region)
    now = timezone.now()
    today = now.date()
    NEXT_WEEK = today + ONE_DAY * 7
    # delete journeys before today
    print('deleting journeys before', today)
    print(Journey.objects.filter(service__region=region, datetime__date__lt=now).delete())
    # get the date of the last generated journey
    last_journey = Journey.objects.filter(service__region=region).order_by('datetime').last()
    if last_journey:
        today = last_journey.datetime.date() + ONE_DAY
        if today > NEXT_WEEK:
            return

    for service in Service.objects.filter(region=region, current=True):
        if region.id == 'NI':
            path = os.path.join(settings.DATA_DIR, 'NI', service.pk + '.json')
            if not os.path.exists(path):
                continue
            groupings = ni.get_data(path)
            day = today
            while day <= NEXT_WEEK:
                do_ni_service(service, groupings, day)
                day += ONE_DAY
            continue

        for i, xml_file in enumerate(get_files_from_zipfile(service)):
            timetable = txc.Timetable(xml_file, None)
            day = today
            while day <= NEXT_WEEK:
                handle_timetable(service, timetable, day)
                day += ONE_DAY


class Command(BaseCommand):
    @staticmethod
    def add_arguments(parser):
        parser.add_argument('regions', nargs='+', type=str)

    def handle(self, regions, *args, **options):
        pool = Pool(processes=4)
        pool.map(handle_region, Region.objects.filter(id__in=regions))

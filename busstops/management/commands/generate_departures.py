import os
from datetime import timedelta, datetime, date
from pytz.exceptions import NonExistentTimeError, AmbiguousTimeError
from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings
from django.utils import timezone
from timetables import txc, northern_ireland
from ...models import Region, Service, Journey, StopUsageUsage, StopPoint
from ...utils import get_files_from_zipfile


ONE_DAY = timedelta(days=1)


def combine_date_time(date, time):
    combo = datetime.combine(date, time)
    try:
        return timezone.make_aware(combo)
    except NonExistentTimeError:
        return timezone.make_aware(combo + timedelta(hours=1))
    except AmbiguousTimeError:
        return timezone.make_aware(combo, is_dst=True)


def handle_timetable(service, timetable, day):
    if not timetable.operating_period.contains(day):
        return
    for grouping in timetable.groupings:
        stops = {row.part.stop.atco_code for row in grouping.rows}
        existent_stops = StopPoint.objects.filter(atco_code__in=stops).values_list('atco_code', flat=True)
        for vj in grouping.journeys:
            if not vj.should_show(day, timetable):
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


def handle_ni_grouping(service, grouping, day):
    for journey in grouping['Journeys']:
        if not northern_ireland.should_show(journey, day):
            continue
        stopusageusages = []
        previous_time = None
        date = day
        for i, su in enumerate(journey['StopUsages']):
            if su['Location'][0] != '7':
                continue
            destination = su['Location']
            if su['Departure']:
                departure = datetime.strptime(su['Departure'], '%H:%M').time()
                if su['Activity'] != 'S':
                    if previous_time and departure < previous_time:
                        date += ONE_DAY
                    stopusageusages.append(
                        StopUsageUsage(datetime=combine_date_time(date, departure),
                                       order=i, stop_id=su['Location'])
                    )
                previous_time = departure
        journey = Journey(service=service, datetime=stopusageusages[0].datetime, destination_id=destination)
        journey.save()
        for suu in stopusageusages:
            suu.journey = journey
        StopUsageUsage.objects.bulk_create(stopusageusages)


def do_ni_service(service, groupings, day):
    for grouping in groupings:
        if grouping['Journeys']:
            handle_ni_grouping(service, grouping, day)


@transaction.atomic
def handle_region(region):
    today = date.today()
    if region.id == 'NI':
        NEXT_WEEK = today + ONE_DAY * 7
    else:  # not actually next week
        NEXT_WEEK = today + ONE_DAY * 2
    # delete journeys before today
    Journey.objects.filter(service__region=region, datetime__date__lt=today).delete()
    # get the date of the last generated journey
    last_journey = Journey.objects.filter(service__region=region).order_by('datetime').last()
    if last_journey:
        today = last_journey.datetime.astimezone(timezone.get_current_timezone()).date() + ONE_DAY
        if today > NEXT_WEEK:
            return

    for service in Service.objects.filter(region=region, current=True):
        if region.id == 'NI':
            path = os.path.join(settings.DATA_DIR, 'NI', service.pk + '.json')
            if not os.path.exists(path):
                continue
            groupings = northern_ireland.get_data(path)
            day = today
            while day <= NEXT_WEEK:
                do_ni_service(service, groupings, day)
                day += ONE_DAY
        else:
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
        for region in Region.objects.filter(id__in=regions):
            handle_region(region)

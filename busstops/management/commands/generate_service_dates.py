from datetime import date, timedelta
from django.core.management.base import BaseCommand
from timetables.txc import TransXChange
from ...models import Service, ServiceDate


def has_times(grouping):
    if grouping.rows:
        return grouping.rows[0].times


def try_day(day, transxchanges):
    for transxchange in transxchanges:
        if transxchange.operating_period.contains(day):
            for journey in transxchange.journeys:
                if journey.should_show(day, transxchange):
                    return True


def handle_services(services):
    today = date.today()
    for service in services.filter(current=True, show_timetable=True, timetable_wrong=False, journey=None):
        day = today
        days = 0
        tried_days = 0

        transxchanges = [TransXChange(file) for file in service.get_files_from_zipfile()]

        while days < 7 and tried_days < 100:
            if try_day(day, transxchanges):
                ServiceDate.objects.update_or_create(service=service, date=day)
                days += 1
            day += timedelta(days=1)
            tried_days += 1


class Command(BaseCommand):
    def handle(self, *args, **options):
        today = date.today()
        ServiceDate.objects.filter(date__lt=today).delete()
        handle_services(Service.objects)

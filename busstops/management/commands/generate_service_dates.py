from datetime import date, timedelta
from django.core.management.base import BaseCommand
from ...models import Service, ServiceDate


def has_times(grouping):
    if grouping.rows:
        return grouping.rows[0].times


def handle_services(services):
    today = date.today()
    for service in services.filter(current=True, show_timetable=True, timetable_wrong=False, journey=None):
        day = today
        days = 0
        tried_days = 0

        while days < 7 and tried_days < 100:
            timetable = service.get_timetable(day)
            if timetable and any(has_times(grouping) for grouping in timetable.groupings):
                ServiceDate.objects.update_or_create(service=service, date=day)
                days += 1
            day += timedelta(days=1)
            tried_days += 1


class Command(BaseCommand):
    def handle(self, *args, **options):
        today = date.today()
        ServiceDate.objects.filter(date__lt=today).delete()
        handle_services(Service.objects)

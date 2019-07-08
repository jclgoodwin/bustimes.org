from datetime import date, timedelta
from django.core.management.base import BaseCommand
from ...models import Service, ServiceDate


def has_times(grouping):
    if grouping.rows:
        return grouping.rows[0].times


def handle_services(services):
    for service in services.filter(current=True, show_timetable=True, timetable_wrong=False, journey=None):
        today = date.today()
        days = 0
        tried_days = 0

        while days < 7 and tried_days < 100:
            timetable = service.get_timetable(today)
            if timetable and any(has_times(grouping) for grouping in timetable.groupings):
                ServiceDate.objects.update_or_create(service=service, date=today)
                days += 1
                break
            today += timedelta(days=1)
            tried_days += 1


class Command(BaseCommand):
    def handle(self, *args, **options):
        ServiceDate.objects.filter(date__lt=date.today()).delete()
        handle_services(Service.objects)

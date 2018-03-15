from datetime import date, timedelta
from django.core.management.base import BaseCommand
from ...models import Service, ServiceDate


class Command(BaseCommand):
    @staticmethod
    def has_times(grouping):
        if grouping.rows:
            return grouping.rows[0].times

    def handle(self, *args, **options):
        ServiceDate.objects.filter(date__lt=date.today()).delete()
        for service in Service.objects.filter(current=True, show_timetable=True, journey=None):
            today = date.today()
            days = 0
            tried_days = 0

            while days < 7 and tried_days < 100:
                timetables = service.get_timetables(today)
                if timetables:
                    for timetable in timetables:
                        if any(self.has_times(grouping) for grouping in timetable.groupings):
                            ServiceDate.objects.update_or_create(service=service, date=today)
                            days += 1
                            break
                today += timedelta(days=1)
                tried_days += 1

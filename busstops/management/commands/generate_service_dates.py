from datetime import date, timedelta
from django.core.management.base import BaseCommand
from ...models import Service, ServiceDate
from ...utils import timetable_from_service


class Command(BaseCommand):
    def handle(self, *args, **options):
        ServiceDate.objects.filter(date__lt=date.today()).delete()
        for service in Service.objects.filter(current=True, show_timetable=True, journey=None, servicedate=None):
            today = date.today()
            days = 0
            tried_days = 0

            while days < 7 and tried_days < 100:
                timetables = timetable_from_service(service, today)
                if timetables:
                    for timetable in timetables:
                        if any(grouping.rows and grouping.rows[0].times for grouping in timetable.groupings):
                            ServiceDate.objects.update_or_create(service=service, date=today)
                            days += 1
                            break
                today += timedelta(days=1)
                tried_days += 1

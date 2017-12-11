from datetime import date, timedelta
from django.core.management.base import BaseCommand
from ...models import Service, ServiceDate
from ...utils import timetable_from_service


class Command(BaseCommand):
    @staticmethod
    def grouping_has_times(grouping):
        if hasattr(grouping, 'rows_list'):
            return grouping.rows_list and grouping.rows_list[0].times
        if grouping.rows and type(grouping.rows) is list:
            return grouping.rows[0].times

    @classmethod
    def timetables_have_times(cls, timetables, today):
        for timetable in timetables:
            timetable.set_date(today)
            for grouping in timetable.groupings:
                if cls.grouping_has_times(grouping):
                    return True

    def handle(self, *args, **options):
        ServiceDate.objects.filter(date__lt=date.today()).delete()
        for service in Service.objects.filter(current=True, show_timetable=True, journey=None, servicedate=None):
            today = date.today()
            days = 0
            tried_days = 0

            timetables = timetable_from_service(service, today)
            while days < 7 and tried_days < 100:
                if self.timetables_have_times(timetables, today):
                    ServiceDate.objects.update_or_create(service=service, date=today)
                    days += 1
                today += timedelta(days=1)
                tried_days += 1

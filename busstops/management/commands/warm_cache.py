import time
from django.core.management.base import BaseCommand
from ...models import Service
from ...utils import timetable_from_service


class Command(BaseCommand):
    def handle(self, *args, **options):
        for service in Service.objects.filter(current=True):
            print(service)
            start = time.time()
            timetable_from_service(service)
            end = time.time()
            print(end - start)

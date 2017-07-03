from django.core.management.base import BaseCommand
from ...search_indexes import ServiceIndex
from ...models import Service


class Command(BaseCommand):
    def handle(self, *args, **options):
        service_index = ServiceIndex()
        for service in Service.objects.filter(current=False):
            service_index.remove_object(service)

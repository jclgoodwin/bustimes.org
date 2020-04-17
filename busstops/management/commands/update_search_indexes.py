from django.core.management.base import BaseCommand
from ...models import Locality, Operator, Service


class Command(BaseCommand):
    def handle(self, *args, **options):

        for locality in Locality.objects.all():
            locality.update_search_vector()

        for operator in Operator.objects.filter(service__current=True).distinct():
            operator.update_search_vector()

        for service in Service.objects.filter(current=True):
            service.update_search_vector()

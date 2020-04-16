from django.core.management.base import BaseCommand
from ...models import Locality, Operator, Service


class Command(BaseCommand):
    def handle(self, *args, **options):

        for locality in Locality.objects.filter(search_vector=None):
            locality.update_search_vector()
            print(locality)

        for operator in Operator.objects.filter(search_vector=None):
            operator.update_search_vector()
            print(operator)

        for service in Service.objects.filter(current=True, search_vector=None):
            service.update_search_vector()
            print(service)

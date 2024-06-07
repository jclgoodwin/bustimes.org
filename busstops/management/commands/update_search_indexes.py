from django.core.management.base import BaseCommand

from ...models import Locality, Operator, Service


class Command(BaseCommand):
    def handle(self, *args, **options):
        to_update = []

        for locality in Locality.objects.with_documents():
            if locality.search_vector != locality.document:
                locality.search_vector = locality.document
                to_update.append(locality)

        Locality.objects.bulk_update(to_update, ["search_vector"])
        to_update = []

        for operator in Operator.objects.with_documents():
            if operator.search_vector != operator.document:
                operator.search_vector = operator.document
                to_update.append(locality)

        Operator.objects.bulk_update(to_update, ["search_vector"])
        to_update = []

        for service in Service.objects.with_documents().filter(current=True):
            if service.search_vector != service.document:
                service.search_vector = service.document
                to_update.append(service)

        Service.objects.bulk_update(to_update, ["search_vector"])
        to_update = []

from tqdm import tqdm
from django.core.management.base import BaseCommand
from django.db.models import Exists, OuterRef
from ...models import Locality, Operator, Service


class Command(BaseCommand):
    def handle(self, *args, **options):
        for locality in tqdm(Locality.objects.with_documents()):
            locality.search_vector = locality.document
            locality.save(update_fields=['search_vector'])

        has_services = Exists(Service.objects.filter(current=True, operator=OuterRef('pk')))
        for operator in tqdm(Operator.objects.with_documents().filter(has_services)):
            operator.search_vector = operator.document
            operator.save(update_fields=['search_vector'])

        print(Operator.objects.filter(~has_services).update(search_vector=None))

        for service in tqdm(Service.objects.with_documents().filter(current=True)):
            service.search_vector = service.document
            service.save(update_fields=['search_vector'])

        print(Service.objects.filter(current=False).update(search_vector=None))

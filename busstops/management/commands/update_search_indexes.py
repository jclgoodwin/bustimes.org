from django.core.management.base import BaseCommand

from ...models import Locality, Operator, Service


class Command(BaseCommand):
    def handle(self, *args, **options):
        for queryset in (
            Locality.objects.with_documents(),
            Operator.objects.with_documents(),
            Service.objects.with_documents().filter(current=True),
        ):
            to_update = []
            for item in queryset:
                if item.search_vector != item.document:
                    item.search_vector = item.document
                    to_update.append(item)

            queryset.bulk_update(to_update, ["search_vector"])

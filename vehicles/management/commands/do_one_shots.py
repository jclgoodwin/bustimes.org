from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.db.models import Exists, OuterRef, Value
from django.db.models.functions import Replace
from django.utils import timezone
from busstops.models import ServiceCode, SIRISource
from ...views import schemes, siri_one_shot


class Command(BaseCommand):
    def handle(self, *args, **options):
        while True:
            codes = ServiceCode.objects.filter(scheme__in=schemes, service__current=True)
            codes = codes.annotate(source_name=Replace('scheme', Value(' SIRI')))
            siri_sources = SIRISource.objects.filter(name=OuterRef('source_name'))
            codes = codes.filter(Exists(siri_sources))

            now = timezone.localtime()
            for code in codes:
                if cache.get(f'{code.service_id}:connected'):
                    print(code)
                    siri_one_shot(code, now)

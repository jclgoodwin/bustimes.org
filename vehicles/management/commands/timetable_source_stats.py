from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.db.models import Count, Q
from django.utils import timezone
from ...models import DataSource


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        now = timezone.now()

        sources = DataSource.objects.annotate(
            count=Count('route__service', filter=Q(route__service__current=True), distinct=True),
        ).filter(count__gt=0).order_by('name')

        stats = {
            "datetime": now,
            "sources": {}
        }
        for source in sources:
            name = source.name
            if '_' in name:
                name = source.name.split('_')[0]
            elif name.startswith('Stagecoach'):
                name = 'Stagecoach'

            if name in stats['sources']:
                stats['sources'][name] += source.count
            else:
                stats['sources'][name] = source.count

        history = cache.get("timetable-source-stats", [])
        history = history[-3000:]

        history.append(stats)

        cache.set("timetable-source-stats", history, None)

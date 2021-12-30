import json
from datetime import timedelta
from ciso8601 import parse_datetime
from tqdm import tqdm

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from vehicles.utils import redis_client
from vehicles.models import VehicleJourney


one_day = timedelta(days=1)


class Command(BaseCommand):
    def handle(self, **options):
        directory = settings.DATA_DIR / 'journeys'

        if not directory.exists():
            directory.mkdir()

        week_ago = timezone.localdate() - timedelta(days=7)

        for journey in tqdm(VehicleJourney.objects.filter(datetime__date__gte=week_ago).only('id')):
            redis_key = f'journey{journey.id}'
            locations = redis_client.lrange(redis_key, 0, -1)
            if locations:
                last = json.loads(locations[-1])
                age = timezone.now() - parse_datetime(last[0])
                if age > one_day:
                    locations = b'\n'.join(locations)
                    path = journey.get_path()
                    path.write_bytes(locations)
                    redis_client.delete(redis_key)

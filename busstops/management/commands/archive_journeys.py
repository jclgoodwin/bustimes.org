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

        today = timezone.localdate()
        while_ago = today - timedelta(days=10)

        while while_ago < today:
            journeys = VehicleJourney.objects.filter(datetime__date=while_ago).only('id')

            pipe = redis_client.pipeline(transaction=False)
            for journey in journeys:
                pipe.exists(f'journey{journey.id}')
            exists = pipe.execute()
            #exists = redis_client.exists(*[f'journey{journey.id}' for journey in journeys])
            #print(exists)

            for i, journey in enumerate(tqdm(journeys)):
                if not exists[i]:
                    continue
                redis_key = f'journey{journey.id}'
                locations = redis_client.lrange(redis_key, 0, -1)
                assert locations
                last = json.loads(locations[-1])
                age = timezone.now() - parse_datetime(last[0])
                if age > one_day:
                            locations = b'\n'.join(locations)
                            path = journey.get_path()
                            path.write_bytes(locations)
                            redis_client.delete(redis_key)

            while_ago += timedelta(days=1)

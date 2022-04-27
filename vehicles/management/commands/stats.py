from datetime import timedelta
from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.utils import timezone
from ...models import VehicleEdit, VehicleJourney


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        now = timezone.now()
        half_hour_ago = now - timedelta(minutes=30)
        journeys = VehicleJourney.objects.filter(latest_vehicle__isnull=False, datetime__gte=half_hour_ago)

        stats = {
            "datetime": now,
            "pending_vehicle_edits": VehicleEdit.objects.filter(approved=None).count(),
            "vehicle_journeys": journeys.count(),
            "service_vehicle_journeys": journeys.filter(service__isnull=False).count(),
            "trip_vehicle_journeys": journeys.filter(trip__isnull=False).count(),
        }

        history = cache.get("vehicle-tracking-stats", [])

        history = history[-3000:] + [stats]

        cache.set("vehicle-tracking-stats", history, None)

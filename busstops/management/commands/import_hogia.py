import requests
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from django.utils import timezone
from ...models import DataSource, Vehicle, VehicleLocation


class Command(BaseCommand):
    def handle(self, *args, **options):
        now = timezone.now()

        source, _ = DataSource.objects.update_or_create({
            'url': 'http://ncc.hogiacloud.com/map/VehicleMapService/Vehicles',
            'datetime': now
        }, name='NCC Hogia')

        session = requests.Session()

        for item in session.get(source.url, timeout=100).json():
            vehicle, _ = Vehicle.objects.update_or_create(
               source=source,
               code=item['Label'].split(': ')[0]
            )
            location = VehicleLocation(
                datetime=now,
                vehicle=vehicle,
                source=source,
                latlong=Point(item['Longitude'], item['Latitude']),
                data=item
            )
            location.save()

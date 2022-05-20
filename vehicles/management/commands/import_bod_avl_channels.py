from ciso8601 import parse_datetime
from asgiref.sync import async_to_sync
from django.core.cache import cache
from django.utils import timezone
from channels.layers import get_channel_layer
from .import_bod_avl import Command as ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    identifiers = None

    @async_to_sync
    async def send_items(self, items):
        await get_channel_layer().send('sirivm', {
            'type': 'sirivm',
            'items': items,
            'when': self.when
        })

    def update(self):
        items = self.get_items() or []

        # encourage items to be grouped by operator
        items.sort(key=lambda item: item['MonitoredVehicleJourney']['OperatorRef'])

        if not self.identifiers:  # restore backup
            self.identifiers = cache.get('bod_avl_identifiers', {})

        i = 0
        to_send = []

        for item in items:
            monitored_vehicle_journey = item['MonitoredVehicleJourney']
            key = f"{monitored_vehicle_journey['OperatorRef']}-{monitored_vehicle_journey['VehicleRef']}"
            if key not in self.identifiers or self.identifiers[key] < item['RecordedAtTime']:
                if key in self.identifiers:
                    assert parse_datetime(self.identifiers[key]) < parse_datetime(item['RecordedAtTime'])
                self.identifiers[key] = item['RecordedAtTime']
                to_send.append(item)
                i += 1
                if i % 1000 == 0:
                    self.send_items(to_send)
                    to_send = []
        if to_send:
            self.send_items(to_send)

        count = len(items)

        # stats for last 10 updates
        bod_status = cache.get('bod_avl_status', [])
        bod_status.append((timezone.now(), self.source.datetime, count, i))
        bod_status = bod_status[-50:]
        cache.set('bod_avl_status', bod_status)

        cache.set('bod_avl_identifiers', self.identifiers)  # backup

        # if i == 0:
        #     return 11

        return 32

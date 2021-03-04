from asgiref.sync import async_to_sync
from django.utils import timezone
from django.core.cache import cache
from channels.layers import get_channel_layer
from channels.exceptions import ChannelFull
from .import_bod_avl import Command as ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    @async_to_sync
    async def send_items(self, items):
        await get_channel_layer().send('sirivm', {
            'type': 'sirivm',
            'items': items,
            'when': self.when
        })

    def update(self):
        now = timezone.now()

        items = self.get_items()
        if not items:
            return 300  # wait five minutes

        cache.set('bod_avl_updated', self.when)
        cache.set('bod_avl_items', len(items))

        # encourage items to be grouped by operator
        items.sort(key=lambda item: item['MonitoredVehicleJourney']['OperatorRef'])

        identifiers = {}
        i = 0
        to_send = []

        for item in items:
            monitored_vehicle_journey = item['MonitoredVehicleJourney']
            key = f"{monitored_vehicle_journey['OperatorRef']}-{monitored_vehicle_journey['VehicleRef']}"
            if self.identifiers.get(key) != item['RecordedAtTime']:
                identifiers[key] = item['RecordedAtTime']
                to_send.append(item)
                i += 1
                if i % 1000 == 0:
                    try:
                        self.send_items(to_send)
                    except ChannelFull:
                        break
                    self.identifiers.update(identifiers)
                    identifiers = {}
                    to_send = []
        if to_send:
            try:
                self.send_items(to_send)
                self.identifiers.update(identifiers)
            except ChannelFull:
                pass

        cache.set('bod_avl_updated_items', i)

        time_taken = timezone.now() - now
        print(time_taken)
        time_taken = time_taken.total_seconds()
        if time_taken < self.wait:
            return self.wait - time_taken
        return 0  # took longer than self.wait

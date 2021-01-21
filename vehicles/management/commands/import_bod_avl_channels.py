from django.utils import timezone
from asgiref.sync import async_to_sync
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

        # encourage items to be grouped by operator
        items.sort(key=lambda item: item['MonitoredVehicleJourney']['OperatorRef'])

        identifiers = {}
        i = 0
        chunks = [[]]

        for item in items:
            monitored_vehicle_journey = item['MonitoredVehicleJourney']
            key = f"{monitored_vehicle_journey['OperatorRef']}-{monitored_vehicle_journey['VehicleRef']}"
            if self.identifiers.get(key) != item['RecordedAtTime']:
                identifiers[key] = item['RecordedAtTime']
                i += 1
                if i == 50:
                    chunks.append([])
                    i = 0
                chunks[-1].append(item)
        try:
            for chunk in chunks:
                self.send_items(chunk)
        except ChannelFull:
            pass

        self.identifiers.update(identifiers)  # channel wasn't full

        time_taken = timezone.now() - now
        print(time_taken)
        time_taken = time_taken.total_seconds()
        if time_taken < self.wait:
            return self.wait - time_taken
        return 0  # took longer than self.wait

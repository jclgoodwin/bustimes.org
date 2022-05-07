from sentry_sdk import capture_exception
from ciso8601 import parse_datetime
from channels.consumer import SyncConsumer
from django.core.cache import cache
from .management.commands import import_bod_avl


class SiriConsumer(SyncConsumer):
    command = None

    def sirivm(self, message):
        try:
            if self.command is None:
                self.command = import_bod_avl.Command().do_source()

            response_timestamp = parse_datetime(message["when"])

            vehicle_cache_keys = [self.command.get_vehicle_cache_key(item) for item in message["items"]]

            vehicle_ids = cache.get_many(vehicle_cache_keys)  # code: id

            vehicles = self.command.vehicles.in_bulk(vehicle_ids.values())  # id: vehicle
            self.command.vehicle_cache = {  # code: vehicle
                key: vehicles[vehicle_id] for key, vehicle_id in vehicle_ids.items() if vehicle_id in vehicles
            }

            for item in message["items"]:
                self.command.handle_item(item, response_timestamp)

            self.command.save()

            to_set = {
                key: value
                for key, value in self.command.vehicle_id_cache.items()
                if key not in vehicle_ids or value != vehicle_ids[key]
            }
            if to_set:
                cache.set_many(to_set, 43200)
        except Exception as e:
            capture_exception(e)
            raise Exception

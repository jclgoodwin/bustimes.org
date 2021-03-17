import beeline
from sentry_sdk import capture_exception
from beeline.middleware.django import HoneyDBWrapper
from contextlib import ExitStack
from ciso8601 import parse_datetime
from django.utils.timezone import now
from channels.consumer import SyncConsumer
from django.core.cache import cache
from django.db import connections
from .management.commands import import_bod_avl


class SiriConsumer(SyncConsumer):
    command = None

    def sirivm(self, message):
        try:
            with beeline.tracer(name="sirivm"):
                if self.command is None:
                    self.command = import_bod_avl.Command().do_source()

                response_timestamp = parse_datetime(message["when"])
                beeline.add_context({
                    "items_count": len(message["items"]),
                    "age": (now() - response_timestamp).total_seconds()
                })

                vehicle_cache_keys = [self.command.get_vehicle_cache_key(item) for item in message["items"]]

                with beeline.tracer(name="cache get many"):
                    vehicle_ids = cache.get_many(vehicle_cache_keys)  # code: id

                with beeline.tracer(name="vehicles in bulk"):
                    vehicles = self.command.vehicles.in_bulk(vehicle_ids.values())  # id: vehicle
                    self.command.vehicle_cache = {  # code: vehicle
                        key: vehicles[vehicle_id] for key, vehicle_id in vehicle_ids.items() if vehicle_id in vehicles
                    }

                with beeline.tracer(name="handle items"):
                    for item in message["items"]:
                        self.command.handle_item(item, response_timestamp)

                with beeline.tracer(name="save"):
                    db_wrapper = HoneyDBWrapper()
                    with ExitStack() as stack:
                        for connection in connections.all():
                            stack.enter_context(connection.execute_wrapper(db_wrapper))
                        self.command.save()

                with beeline.tracer(name="set many"):
                    cache.set_many({
                        key: value
                        for key, value in self.command.vehicle_id_cache.items()
                        if key not in vehicle_ids or value != vehicle_ids[key]
                    }, 43200)
        except Exception as e:
            capture_exception(e)
            raise Exception

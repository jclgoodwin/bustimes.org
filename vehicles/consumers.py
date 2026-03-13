import asyncio
import json
import logging
from uuid import uuid4

import redis.asyncio as aioredis
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

from .utils import tile38_client

logger = logging.getLogger(__name__)


class VehicleLocationConsumer(AsyncWebsocketConsumer):
    _listen_task = None
    _pubsub_client = None
    chan_name = None

    async def connect(self):
        await self.accept()

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            min_lat, min_lon, max_lat, max_lon = data["bounds"]
        except (KeyError, ValueError, TypeError):
            await self.close()
            return

        await self._cleanup()

        self.chan_name = f"vehicles_{uuid4().hex}"

        await (
            tile38_client.setchan(self.chan_name)
            .within("vehicle_location_locations")
            .bounds(min_lat, min_lon, max_lat, max_lon)
            .detect(["enter", "exit", "inside"])
            .commands(["set"])
            .activate()
        )

        self._pubsub_client = aioredis.from_url(
            settings.TILE38_URL, decode_responses=True
        )
        pubsub = self._pubsub_client.pubsub()
        await pubsub.subscribe(self.chan_name)

        self._listen_task = asyncio.create_task(self._listen(pubsub))

    async def _listen(self, pubsub):
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    await self.send(message["data"])
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception(e)

    async def disconnect(self, code):
        await self._cleanup()

    async def _cleanup(self):
        if self._listen_task:
            self._listen_task.cancel()
            self._listen_task = None
        if self._pubsub_client:
            await self._pubsub_client.aclose()
            self._pubsub_client = None
        if self.chan_name:
            from .utils import tile38_client

            if tile38_client:
                try:
                    await tile38_client.delchan(self.chan_name)
                except Exception as e:
                    logger.exception(e)
            self.chan_name = None

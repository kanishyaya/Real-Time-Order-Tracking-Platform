"""
redis_broadcaster.py
--------------------
Subscribes to Redis and broadcasts every event to all WebSocket clients.

FIX: Uses a separate Redis connection for pub/sub (required by redis-py).
The shared client is for publishing only. Subscribing on the same client
caused the listen() loop to block or miss messages.
"""

import asyncio
import json
import logging

import redis.asyncio as aioredis

from config            import settings
from websocket_manager import ConnectionManager

logger = logging.getLogger(__name__)


async def start_redis_broadcaster(
    redis_client: aioredis.Redis,
    manager: ConnectionManager,
) -> None:
    logger.info("Redis Broadcaster: starting…")

    while True:
        try:
            # Create a DEDICATED connection for pub/sub — required by Redis protocol.
            # The main redis_client is used only for PUBLISH. Using the same
            # connection for both publish and subscribe causes missed messages.
            sub_client = await aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
            )
            pubsub = sub_client.pubsub()
            await pubsub.subscribe(settings.REDIS_CHANNEL)
            logger.info("Redis Broadcaster: subscribed to '%s'", settings.REDIS_CHANNEL)

            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                try:
                    event = json.loads(message["data"])
                    logger.info(
                        "Redis Broadcaster: %s → broadcasting to %d client(s)",
                        event.get("operation"), manager.count,
                    )
                    await manager.broadcast(event)
                except Exception as exc:
                    logger.error("Redis Broadcaster: broadcast error — %s", exc)

        except asyncio.CancelledError:
            logger.info("Redis Broadcaster: cancelled.")
            break
        except Exception as exc:
            logger.error("Redis Broadcaster: error — %s. Restarting in 2s…", exc)
            await asyncio.sleep(2)
        finally:
            try:
                await pubsub.unsubscribe()
                await sub_client.aclose()
            except Exception:
                pass

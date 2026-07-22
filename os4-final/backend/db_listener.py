"""
db_listener.py
--------------
Listens on PostgreSQL 'order_updates' and publishes to Redis.

FIXES:
1. handle_notification is defined OUTSIDE the inner while loop so the
   closure captures the correct conn reference and isn't redefined on
   every iteration.
2. Uses asyncio.wait_for with a raw connection keepalive — no sleep(1)
   polling that blocked the event loop.
3. asyncpg LISTEN callbacks are dispatched immediately on the event
   loop — zero added latency.
"""

import asyncio
import json
import logging

import asyncpg
import redis.asyncio as aioredis

from config       import settings
from redis_pubsub import publish_event

logger = logging.getLogger(__name__)
total_events_fired: int = 0


async def start_db_listener(redis_client: aioredis.Redis) -> None:
    global total_events_fired

    while True:
        conn = None
        try:
            logger.info("DB Listener: connecting to PostgreSQL…")
            conn = await asyncpg.connect(dsn=settings.DATABASE_URL)
            logger.info("DB Listener: connected. Listening on 'order_updates'…")

            # Define the callback ONCE per connection — not inside a loop
            async def handle_notification(connection, pid, channel, payload):
                global total_events_fired
                try:
                    event = json.loads(payload)
                    await publish_event(redis_client, event)
                    total_events_fired += 1
                    logger.info(
                        "DB Listener: %s order #%s → published to Redis",
                        event.get("operation"),
                        event.get("data", {}).get("id"),
                    )
                except Exception as exc:
                    logger.error("DB Listener: error handling notification — %s", exc)

            await conn.add_listener("order_updates", handle_notification)

            # Keep alive with a long sleep — asyncpg fires handle_notification
            # immediately via the event loop without any polling needed.
            # We only wake up to check if the connection died.
            while not conn.is_closed():
                await asyncio.sleep(5)
                try:
                    await asyncio.wait_for(conn.fetchval("SELECT 1"), timeout=3.0)
                except (asyncio.TimeoutError, Exception):
                    logger.warning("DB Listener: connection lost, reconnecting…")
                    break

        except asyncio.CancelledError:
            logger.info("DB Listener: cancelled.")
            break
        except Exception as exc:
            logger.warning("DB Listener: %s — reconnecting in 2s…", exc)
            await asyncio.sleep(2)
        finally:
            if conn:
                try:
                    if not conn.is_closed():
                        await conn.close()
                except Exception:
                    pass

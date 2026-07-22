"""
redis_pubsub.py
---------------
Thin wrapper around the Redis Pub/Sub interface.

Publisher  — used by the DB listener to push events onto the channel.
Subscriber — used by the WebSocket gateway to receive events.

Keeping publish and subscribe as separate async contexts makes the
architecture decoupled: the DB listener and the WebSocket server are
independent services that only share a Redis channel name.
"""

import json
import redis.asyncio as aioredis

from config import settings


# ── Client factory ───────────────────────────────────────────


async def create_redis_client() -> aioredis.Redis:
    """Create and return an async Redis client."""

    client = await aioredis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
    )

    return client


# ── Publisher ────────────────────────────────────────────────


async def publish_event(client: aioredis.Redis, event: dict) -> None:
    """
    Publish a JSON-serialised event to the shared Redis channel.
    Called by the DB listener each time PostgreSQL fires a NOTIFY.
    """

    message = json.dumps(event)

    await client.publish(settings.REDIS_CHANNEL, message)


# ── Subscriber ───────────────────────────────────────────────


async def subscribe_to_events(client: aioredis.Redis):
    """
    Return an active pubsub subscriber on the order_updates channel.
    The caller iterates over messages as they arrive.
    """

    pubsub = client.pubsub()

    await pubsub.subscribe(settings.REDIS_CHANNEL)

    return pubsub

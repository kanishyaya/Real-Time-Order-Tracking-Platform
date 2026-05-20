"""
websocket_manager.py
--------------------
Manages ALL active WebSocket connections across every portal.

Because every portal (port 4000, 4001, 4002, …) connects back to the
SAME backend process, all connections land here.  When a broadcast fires
(e.g. an order status change), every connected client on every portal
receives the update in one pass — with no polling and no page refresh.

Responsibilities:
  - Track every connected client by a unique UUID.
  - Broadcast messages to ALL clients simultaneously.
  - Handle clean connect / disconnect lifecycle.
  - Expose a client count for the /metrics endpoint.
"""

import asyncio
import logging

from fastapi import WebSocket


logger = logging.getLogger(__name__)


class ConnectionManager:
    """Registry of every active WebSocket connection across all portals."""

    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}
        self._lock = asyncio.Lock()

    # ── Lifecycle ──────────────────────────────────────────────────────────

    async def connect(self, client_id: str, websocket: WebSocket) -> None:
        """Accept and register a new WebSocket client."""
        await websocket.accept()
        async with self._lock:
            self._connections[client_id] = websocket
        logger.info(
            "WebSocket: client %s connected  (total across all portals: %d)",
            client_id, self.count,
        )

    async def disconnect(self, client_id: str) -> None:
        """Remove a client from the registry."""
        async with self._lock:
            self._connections.pop(client_id, None)
        logger.info(
            "WebSocket: client %s disconnected (total across all portals: %d)",
            client_id, self.count,
        )

    # ── Messaging ──────────────────────────────────────────────────────────

    async def send_to_client(self, client_id: str, message: dict) -> None:
        """Send a JSON message to a specific client."""
        websocket = self._connections.get(client_id)
        if websocket:
            try:
                await websocket.send_json(message)
            except Exception as exc:
                logger.warning("WebSocket: failed to send to %s — %s", client_id, exc)
                await self.disconnect(client_id)

    async def broadcast(self, message: dict) -> None:
        """
        Send a JSON message to EVERY connected client on EVERY portal.

        This is the core of the real-time sync: one event from Postgres
        flows through Redis and then fans out here to every browser tab,
        on every port, simultaneously — no polling, no refresh required.
        """
        clients = list(self._connections.items())   # snapshot before iteration

        if clients:
            logger.info(
                "WebSocket: broadcasting to %d client(s) across all portals",
                len(clients),
            )

        await asyncio.gather(*[
            self._safe_send(cid, ws, message)
            for cid, ws in clients
        ])

    async def _safe_send(
        self, client_id: str, websocket: WebSocket, message: dict
    ) -> None:
        """Send to one client; silently remove it if the connection is dead."""
        try:
            await websocket.send_json(message)
        except Exception:
            await self.disconnect(client_id)

    # ── Metrics ────────────────────────────────────────────────────────────

    @property
    def count(self) -> int:
        """Total number of connected clients across all portals."""
        return len(self._connections)

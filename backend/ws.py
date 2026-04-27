"""WebSocket connection manager: tracks active clients, broadcasts events."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import WebSocket
from pydantic import BaseModel

log = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(ws)

    async def send(self, ws: WebSocket, event: BaseModel | dict[str, Any]) -> None:
        payload = event.model_dump() if isinstance(event, BaseModel) else event
        await ws.send_json(payload)

    async def broadcast(self, event: BaseModel | dict[str, Any]) -> None:
        payload = event.model_dump() if isinstance(event, BaseModel) else event
        async with self._lock:
            stale: list[WebSocket] = []
            for ws in self._connections:
                try:
                    await ws.send_json(payload)
                except Exception:
                    stale.append(ws)
            for ws in stale:
                self._connections.discard(ws)

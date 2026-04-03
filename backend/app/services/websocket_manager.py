from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from fastapi import WebSocket


class WebSocketManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._running: bool = False

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def broadcast(self, message_type: str, data: dict) -> None:
        payload = {
            "type": message_type,
            "data": data,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        stale: list[WebSocket] = []
        for connection in self._connections:
            try:
                await connection.send_json(payload)
            except Exception:
                stale.append(connection)
        for connection in stale:
            self.disconnect(connection)

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def stop(self) -> None:
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

    async def _heartbeat_loop(self) -> None:
        while self._running:
            await asyncio.sleep(30)
            await self.broadcast("heartbeat", {"status": "alive"})


websocket_manager = WebSocketManager()

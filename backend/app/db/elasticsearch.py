from __future__ import annotations


class ElasticsearchClientStub:
    def __init__(self) -> None:
        self.connected: bool = False

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    async def ping(self) -> bool:
        return self.connected


elasticsearch_client = ElasticsearchClientStub()

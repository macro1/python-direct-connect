import asyncio
import logging

logger = logging.getLogger(__name__)
class Protocol(asyncio.Protocol):

    def connection_made(self, transport: asyncio.Transport):
        self.transport = transport

    def connection_lost(self, exc: Exception | None):
        logger.exception("Connection lost")

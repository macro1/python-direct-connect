import asyncio
import inspect
import logging
import ssl
import weakref
from typing import Iterable, Optional, Protocol, Union

from direct_connect.exceptions import TimeoutError
from direct_connect.nmdc.protocol import NMDCClientProtocol


class Connection:
    _conn: asyncio.Transport

    def __init__(
        self,
        host: str = "localhost",
        port: str | int = 411,
        username: str = "bot",
        password: str | None = None,
        socket_timeout: Optional[float] = None,
        socket_connect_timeout: Optional[float] = None,
    ):
        self.host = host
        self.port = int(port)
        self.username = username
        self.password = password
        self.socket_timeout = socket_timeout
        self.socket_connect_timeout = socket_connect_timeout or socket_timeout
        loop = asyncio.get_running_loop()
        self._on_connected = loop.create_future()
        self._protocol = NMDCClientProtocol(
            on_connected=self._on_connected, on_hub_name=loop.create_future()
        )

    async def connect(self) -> None:
        async with asyncio.timeout(self.socket_connect_timeout):  # type: ignore[attr-defined]
            self._conn, _ = await asyncio.get_event_loop().create_connection(
                lambda: self._protocol,
                host=self.host,
                port=self.port,
            )
            await self._on_connected

    async def send_message(self, message: str) -> None:
        self._protocol.send_message(message)

    async def get_hub_name(self) -> str:
        hub_name = await self._protocol.on_hub_name
        return hub_name.decode()

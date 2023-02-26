import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class Connection:
    _conn: asyncio.Transport
    _reader: asyncio.StreamReader
    _writer: asyncio.StreamWriter
    hub_name: str

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

    async def connect(self) -> None:
        async with asyncio.timeout(self.socket_connect_timeout):  # type: ignore[attr-defined]
            reader, writer = await asyncio.open_connection(
                host=self.host,
                port=self.port,
            )
            while True:
                data = await reader.readuntil(b"|")
                logger.debug(f"connect: {data!r}")
                if data[:6] == b"$Lock ":
                    challenge = data.split(b" ")[1]
                    key = key_from_lock(challenge)
                    writer.write(b"$Supports HubTopic QuickList NoHello|$Key %b|" % key)
                elif data[:10] == b"$Supports ":
                    writer.write(
                        rb"$MyINFO $ALL %b <++ V:0.673,M:P,H:0/1/0,S:2>$ $LAN(T3)0x31$example@example.com$1234$\|"
                        % self.username.encode()
                    )
                elif data[:9] == b"$HubName ":
                    self.hub_name = data[9:-1].decode()
                    break
                else:
                    logger.warning(f"unrecognized: {data!r}")
            await writer.drain()
        self._reader = reader
        self._writer = writer

    async def send_message(self, message: str) -> None:
        ...


def key_from_lock(challenge: bytes) -> bytes:
    key = []
    key.append(
        challenge[0] ^ challenge[len(challenge) - 1] ^ challenge[len(challenge) - 2] ^ 5
    )
    for i in range(1, len(challenge)):
        key.append(challenge[i] ^ challenge[i - 1])
    for i in range(0, len(challenge)):
        key[i] = ((key[i] << 4) & 240) | ((key[i] >> 4) & 15)
    response = b""
    for i in range(0, len(key)):
        if key[i] in (0, 5, 36, 96, 124, 126):
            response += b"/%%DCN%03d%%/" % (key[i],)
        else:
            response += bytes([key[i]])
    return response

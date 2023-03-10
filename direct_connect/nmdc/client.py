import asyncio
import logging
from typing import Optional
from typing import Union

logger = logging.getLogger(__name__)


class NMDC:
    _reader: asyncio.StreamReader
    _writer: asyncio.StreamWriter
    description_comment = "bot"
    description_tag: Optional[str] = None
    description_connection = ""
    description_email = ""
    encoding = "utf_8"

    def __init__(
        self,
        host: str = "localhost",
        nick: str = "bot",
        port: Union[str, int] = 411,
        socket_timeout: Optional[float] = None,
        socket_connect_timeout: Optional[float] = None,
    ):
        self.host = host
        self.port = port
        assert " " not in nick, "NMDC nicks cannot contain spaces"
        self.nick = nick
        self.socket_timeout = socket_timeout
        self.socket_connect_timeout = socket_connect_timeout
        self.hub_name: Optional[str] = None

    async def connect(self) -> None:
        await asyncio.wait_for(self._connect(), self.socket_connect_timeout)

    async def _connect(self) -> None:
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
                writer.write(b"$Key " + key + f"|$ValidateNick {self.nick}|".encode())
            elif data[:7] == b"$Hello ":
                description = []
                if self.description_comment:
                    description.append(self.description_comment)
                if self.description_tag is not None:
                    description.append(f"<{self.description_tag}>")
                writer.write(
                    f"$Version 1.0091|$MyINFO $ALL {self.nick} {' '.join(description)}$ ${self.description_connection}1${self.description_email}$0$|".encode(
                        self.encoding
                    )
                )
            elif data[:9] == b"$HubName ":
                self.hub_name = data[9:-1].decode()
            elif data[:10] == b"$NickList ":
                break
            else:
                logger.warning(f"unrecognized: {data!r}")
        self._reader = reader
        self._writer = writer

    async def send_chat(self, message: str) -> None:
        self._writer.write(
            f"<{self.nick}> {message.replace('&', '&amp;').replace('|', '&#124;')}|".encode(
                self.encoding
            )
        )
        await self._writer.drain()

    async def receive_message(self) -> str:
        message = await self._reader.readuntil(b"|")
        return (
            message[:-1]
            .decode()
            .replace("&#124;", "|")
            .replace("&#36;", "$")
            .replace("&amp;", "&")
        )


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

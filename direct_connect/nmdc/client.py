import asyncio
import logging
from typing import TypedDict
from typing import Union

logger = logging.getLogger(__name__)


class NMDCMessage(TypedDict):
    user: str | None
    message: str


class NMDC:
    _reader: asyncio.StreamReader
    _writer: asyncio.StreamWriter
    description_comment = "bot"
    description_tag: str | None = None
    description_connection = ""
    description_email = ""
    encoding = "utf_8"

    def __init__(
        self,
        host: str = "localhost",
        nick: str = "bot",
        port: Union[str, int] = 411,
        socket_timeout: float | None = None,
        socket_connect_timeout: float | None = None,
    ):
        self.host = host
        self.port = port
        assert " " not in nick, "NMDC nicks cannot contain spaces"
        self.nick = nick
        self.socket_timeout = socket_timeout
        self.socket_connect_timeout = socket_connect_timeout
        self.hub_name: str | None = None

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
        escaped_message = message.replace("&", "&amp;").replace("|", "&#124;")
        prepared_message = f"<{self.nick}> {escaped_message}"
        logger.debug(f"Sending message: {prepared_message}")
        self._writer.write(f"{prepared_message}|".encode(self.encoding))
        await self._writer.drain()

    async def get_message(self) -> NMDCMessage | None:
        raw_message = await self._reader.readuntil(b"|")
        decoded_message = (
            raw_message[:-1]
            .decode()
            .replace("&#124;", "|")
            .replace("&#36;", "$")
            .replace("&amp;", "&")
        )
        logger.debug(f"Received message: {decoded_message}")
        if decoded_message[0] == "<":
            user_name, message = decoded_message[1:].split("> ", 1)
        else:
            user_name = None
            message = decoded_message
        return {"user": user_name, "message": message}

    def close(self) -> None:
        self._writer.close()

    async def wait_closed(self) -> None:
        await self._writer.wait_closed()


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

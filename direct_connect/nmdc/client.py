import asyncio
from typing import TypedDict
from typing import Union
import dataclasses
from direct_connect.nmdc import handlers
from direct_connect.nmdc import logger

@dataclasses.dataclass(slots=True)
class NMDCEvent:
    event_type: str
    message: str
    user: str | None = None

def nmdc_decode(encoded_message: bytes, encoding: str) -> str:
    return (
        encoded_message
        .decode(encoding)
        .replace("&#124;", "|")
        .replace("&#36;", "$")
        .replace("&amp;", "&")
    )


class NMDC:
    _reader: asyncio.StreamReader
    _writer: asyncio.StreamWriter
    description_comment = "bot"
    description_tag: str | None = None
    description_connection = ""
    description_email = ""
    encoding = "utf_8"
    _read_task: asyncio.Task | None = None
    handlers = {
        '$Lock': handlers.connect
    }

    def __init__(
        self,
        host: str = "localhost",
        nick: str = "bot",
        port: Union[str, int] = 411,
        socket_timeout: float | None = None,
        socket_connect_timeout: float | None = None,
    ):
        self.host = host
        self.port = int(port)
        assert " " not in nick, "NMDC nicks cannot contain spaces"
        self.nick = nick
        self.socket_timeout = socket_timeout
        self.socket_connect_timeout = socket_connect_timeout
        self.hub_name: str | None = None

    async def connect(self) -> None:
        await asyncio.wait_for(self._connect(), self.socket_connect_timeout)
        #self._read_task = asyncio.create_task(self.read_forever)

    async def _connect(self) -> None:
        reader, writer = await asyncio.open_connection(
            host=self.host,
            port=self.port,
        )
        writer.transport.set_write_buffer_limits(0)
        self._reader = reader
        self._writer = writer

    def close(self) -> None:
        if self._get_message_task is not None:
            self._get_message_task.cancel()
        self._writer.close()

    async def wait_closed(self) -> None:
        await self._writer.wait_closed()

    async def read_forever(self) -> None:
        while True:
            await asyncio.sleep(1.0)
            await self._writer.drain()
            try:
                raw_event = await asyncio.wait_for(self._reader.readuntil(b'|'), 0.1)
            except TimeoutError:
                continue
            except asyncio.IncompleteReadError as e:
                print(e.partial)
                raise
            print("<- server", raw_event)
            user: str | None = None
            event: NMDCEvent
            type_bytes, message_bytes = raw_event.split(b' ', maxsplit=1)

            event_type = nmdc_decode(type_bytes, self.encoding)
            if event_type[0] == "<":
                event_type = "message"
                user = nmdc_decode(event_type[1:-1], self.encoding)
            try:
                handler = self.handlers[event_type]
            except KeyError:
                logger.debug(f"Unhandled {event_type} event", extra={'raw_event': raw_event})
                continue
            message = nmdc_decode(message_bytes, self.encoding)
            event = NMDCEvent(event_type, message, user)
            asyncio.create_task(handler(self, event))

    async def write(self, message: str) -> None:
        encoded_message = message.encode(self.encoding) + b"|"
        print("-> server", encoded_message)
        self._writer.write(encoded_message)

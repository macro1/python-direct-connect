import asyncio
import dataclasses
from typing import Any
from typing import Callable
from typing import Coroutine
from typing import Union

from direct_connect.nmdc import handlers
from direct_connect.nmdc import logger


@dataclasses.dataclass(slots=True)
class NMDCEvent:
    event_type: str
    message: str
    user: str | None = None


EventHandler = Callable[["NMDC", NMDCEvent], Coroutine[Any, Any, None]]


def nmdc_decode(encoded_message: bytes, encoding: str) -> str:
    return (
        encoded_message.decode(encoding)
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
    _read_task: asyncio.Task[bytes] | None = None
    handlers: dict[str, list[Callable[["NMDC", NMDCEvent], Coroutine[Any, Any, None]]]]

    def __init__(
        self,
        host: str = "localhost",
        nick: str = "",
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
        self.handlers = {"$Lock": [handlers.connect]}

    async def connect(self) -> None:
        await asyncio.wait_for(self._connect(), self.socket_connect_timeout)
        # self._read_task = asyncio.create_task(self.read_forever)

    async def _connect(self) -> None:
        reader, writer = await asyncio.open_connection(
            host=self.host,
            port=self.port,
        )
        writer.transport.set_write_buffer_limits(0)
        self._reader = reader
        self._writer = writer

    def close(self) -> None:
        # if self._get_message_task is not None:
        #     self._get_message_task.cancel()
        self._writer.close()

    async def wait_closed(self) -> None:
        await self._writer.wait_closed()

    async def read_forever(self) -> None:
        tasks: set[asyncio.Task[Any]] = set()
        while True:
            if self._read_task is None:
                self._read_task = asyncio.create_task(self._reader.readuntil(b"|"))
            done, tasks = await asyncio.wait(
                tasks | {self._read_task},
                timeout=1.0,
                return_when=asyncio.FIRST_COMPLETED,
            )
            done.discard(self._read_task)
            for task in done:
                await task
            await self._writer.drain()
            if not self._read_task.done():
                continue
            raw_event = await self._read_task
            self._read_task = None
            print(f"{self.nick} <- server", raw_event)
            user: str | None = None
            event: NMDCEvent
            type_bytes, message_bytes = raw_event.split(b" ", maxsplit=1)

            event_type = nmdc_decode(type_bytes, self.encoding)
            if event_type[0] == "<":
                user = event_type[1:-1]
                event_type = "message"
            try:
                event_handlers = self.handlers[event_type]
            except KeyError:
                logger.debug(
                    f"Unhandled {event_type} event", extra={"raw_event": raw_event}
                )
                continue
            message = nmdc_decode(message_bytes[:-1], self.encoding)
            event = NMDCEvent(event_type, message, user)
            for handler in event_handlers:
                tasks.add(asyncio.create_task(handler(self, event)))

    async def write(self, message: str) -> None:
        encoded_message = message.encode(self.encoding) + b"|"
        print(f"{self.nick} -> server", encoded_message)
        self._writer.write(encoded_message)
        await self._writer.drain()

    async def send_chat(self, message: str) -> None:
        escaped_message = message.replace("&", "&amp;").replace("|", "&#124;")
        prepared_message = f"<{self.nick}> {escaped_message}"
        await self.write(prepared_message)

    def on(self, event_type: str) -> Callable[[EventHandler], EventHandler]:
        def decorator(fn: EventHandler) -> EventHandler:
            try:
                handlers = self.handlers[event_type]
            except KeyError:
                handlers = []
                self.handlers[event_type] = handlers
            handlers.append(fn)
            return fn

        return decorator

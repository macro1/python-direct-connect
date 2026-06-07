import asyncio
import dataclasses
from collections.abc import Callable
from collections.abc import Coroutine
from typing import Any
from typing import Optional
from typing import Union

from direct_connect.exceptions import MessageLimitExceededError
from direct_connect.io import StreamConnection
from direct_connect.nmdc import handlers
from direct_connect.nmdc import logger


@dataclasses.dataclass
class NMDCEvent:
    event_type: str
    message: str
    user: Optional[str] = None


EventHandler = Callable[["NMDC", NMDCEvent], Coroutine[Any, Any, None]]


def nmdc_decode(encoded_message: bytes, encoding: str) -> str:
    return (
        encoded_message.decode(encoding, errors="replace")
        .replace("&#124;", "|")
        .replace("&#36;", "$")
        .replace("&amp;", "&")
    )


class NMDC:
    _conn: StreamConnection
    description_comment = "bot"
    description_tag: Optional[str] = None
    description_connection = ""
    description_email = ""
    handlers: dict[str, list[EventHandler]]
    reconnect_delay: float = 5
    ping_interval: float = 20
    max_message_size: int = 65536

    @property
    def _reader(self) -> asyncio.StreamReader:
        if self._conn._reader is None:
            raise RuntimeError("Not connected")
        return self._conn._reader

    @_reader.setter
    def _reader(self, value: asyncio.StreamReader) -> None:
        self._conn._reader = value

    @property
    def _writer(self) -> asyncio.StreamWriter:
        if self._conn._writer is None:
            raise RuntimeError("Not connected")
        return self._conn._writer

    @_writer.setter
    def _writer(self, value: asyncio.StreamWriter) -> None:
        self._conn._writer = value

    def __init__(
        self,
        host: str = "localhost",
        nick: str = "",
        port: Union[str, int] = 411,
        socket_timeout: Optional[float] = None,
        socket_connect_timeout: Optional[float] = None,
        encoding: str = "utf_8",
    ) -> None:
        self.host = host
        self.port = int(port)
        if " " in nick:
            raise ValueError("NMDC nicks cannot contain spaces")
        self.nick = nick
        self.socket_timeout = socket_timeout
        self.socket_connect_timeout = socket_connect_timeout
        self._conn = StreamConnection(
            host=self.host,
            port=self.port,
            socket_timeout=self.socket_timeout,
            socket_connect_timeout=self.socket_connect_timeout,
        )
        self.hub_name: Optional[str] = None
        self.handlers = {}
        self.encoding = encoding
        # default handlers
        self.on("$Lock")(handlers.connect)
        self.on("$HubName")(handlers.store_hubname)

    async def connect(self) -> None:
        await self._conn.connect()
        logger.info("Connected")

    def close(self) -> Coroutine[Any, Any, None]:
        self._conn.close()
        return self.wait_closed()

    async def wait_closed(self) -> None:
        await self._conn.wait_closed()

    async def listen(self) -> None:
        read_task = asyncio.create_task(
            self._conn.read_until(b"|", self.max_message_size)
        )
        tasks: set[asyncio.Task[Any]] = {read_task}
        while True:
            # Drain before reading so outgoing writes win priority over the
            # next inbound event when the loop is busy.
            await self._conn.drain()

            done, tasks = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

            for task in done:
                if task is read_task:
                    raw_event = await read_task
                    read_task = asyncio.create_task(
                        self._conn.read_until(b"|", self.max_message_size)
                    )
                    tasks.add(read_task)

                    user: Optional[str] = None
                    event: NMDCEvent
                    type_bytes, message_bytes = raw_event.split(b" ", maxsplit=1)

                    event_type = nmdc_decode(type_bytes, self.encoding)
                    if event_type[0] == "<":
                        user = event_type[1:-1]
                        event_type = "message"
                    event_handlers = self.handlers.get(event_type, [handlers.default])
                    message = nmdc_decode(message_bytes[:-1], self.encoding)
                    event = NMDCEvent(event_type, message, user)
                    for handler in event_handlers:
                        handler_task = asyncio.create_task(handler(self, event))
                        tasks.add(handler_task)
                else:
                    await task

    async def ping(self) -> None:
        while True:
            await asyncio.sleep(self.ping_interval)
            await self.write("")

    async def run_forever(self) -> None:
        await self.connect()
        while True:
            try:
                done, pending = await asyncio.wait(
                    {asyncio.create_task(c) for c in (self.ping(), self.listen())},
                    return_when=asyncio.FIRST_EXCEPTION,
                )
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                for task in (
                    done
                ):  # pragma: no branch # done will always have at least one task
                    await task

            except (
                OSError,
                asyncio.IncompleteReadError,
                TimeoutError,
                MessageLimitExceededError,
            ):
                logger.exception(f"Retrying after {self.reconnect_delay}s")
                await asyncio.sleep(self.reconnect_delay)
                await self.connect()

    async def write(self, message: str) -> None:
        encoded_message = message.encode(self.encoding) + b"|"
        logger.info(
            "Sending message to NMDC server",
            extra={"nmdc_nick": self.nick, "nmdc_message": encoded_message},
        )
        self._conn.write(encoded_message)
        await self._conn.drain()

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

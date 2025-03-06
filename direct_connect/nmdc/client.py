import asyncio
import dataclasses
from collections.abc import Callable
from collections.abc import Coroutine
from typing import Any
from typing import Optional
from typing import Union

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
        encoded_message.decode(encoding)
        .replace("&#124;", "|")
        .replace("&#36;", "$")
        .replace("&amp;", "&")
    )


class NMDC:
    _reader: asyncio.StreamReader
    _writer: asyncio.StreamWriter
    description_comment = "bot"
    description_tag: Optional[str] = None
    description_connection = ""
    description_email = ""
    handlers: dict[str, list[EventHandler]]
    reconnect_delay: float = 5
    ping_interval: float = 20

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
        assert " " not in nick, "NMDC nicks cannot contain spaces"
        self.nick = nick
        self.socket_timeout = socket_timeout
        self.socket_connect_timeout = socket_connect_timeout
        self.hub_name: Optional[str] = None
        self.handlers = {}
        self.encoding = encoding
        # default handlers
        self.on("$Lock")(handlers.connect)
        self.on("$HubName")(handlers.store_hubname)

    async def connect(self) -> None:
        await asyncio.wait_for(self._connect(), self.socket_connect_timeout)
        logger.info("Connected")

    async def _connect(self) -> None:
        reader, writer = await asyncio.open_connection(
            host=self.host,
            port=self.port,
        )
        writer.transport.set_write_buffer_limits(0)
        self._reader = reader
        self._writer = writer

    def close(self) -> Coroutine[Any, Any, None]:
        self._writer.close()
        return self.wait_closed()

    async def wait_closed(self) -> None:
        await self._writer.wait_closed()

    async def listen(self) -> None:
        read_task = asyncio.create_task(self._reader.readuntil(b"|"))
        tasks: set[asyncio.Task[Any]] = {read_task}
        while True:
            await self._writer.drain()

            done, tasks = await asyncio.wait(
                tasks, timeout=0.1, return_when=asyncio.FIRST_COMPLETED
            )

            for task in done:
                tasks.discard(task)
                if task is read_task:
                    raw_event = await read_task
                    read_task = asyncio.create_task(self._reader.readuntil(b"|"))
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
            await self._writer.drain()

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
                for (
                    task
                ) in (
                    done
                ):  # pragma: no branch # done will always have at least one task
                    await task

            except (OSError, asyncio.IncompleteReadError):  # pragma: no cover
                while True:
                    logger.error(f"Retrying after {self.reconnect_delay}s")
                    await asyncio.sleep(self.reconnect_delay)
                    try:
                        await self.connect()
                    except OSError:
                        pass
                    else:
                        break

    async def write(self, message: str) -> None:
        encoded_message = message.encode(self.encoding) + b"|"
        logger.info(
            "Sending message to NMDC server",
            extra={"nmdc_nick": self.nick, "nmdc_message": encoded_message},
        )
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

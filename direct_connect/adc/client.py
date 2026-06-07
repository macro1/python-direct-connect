import asyncio
import base64
import dataclasses
import os
import re
from collections.abc import Callable
from collections.abc import Coroutine
from typing import Any
from typing import Optional
from typing import Union

from direct_connect.adc import handlers
from direct_connect.adc import logger
from direct_connect.exceptions import MessageLimitExceededError
from direct_connect.io import StreamConnection
from direct_connect.vendored.tiger import tiger


@dataclasses.dataclass
class ADCEvent:
    prefix: str
    cmd: str
    sender_sid: Optional[str] = None
    args: list[str] = dataclasses.field(default_factory=list)
    tags: dict[str, str] = dataclasses.field(default_factory=dict)


EventHandler = Callable[["ADC", ADCEvent], Coroutine[Any, Any, None]]

TAG_PATTERN = re.compile(r"^[A-Z][A-Z0-9]$")


def adc_escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(" ", "\\s")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )


def adc_unescape(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        char = match.group(1)
        if char == "s":
            return " "
        elif char == "n":
            return "\n"
        elif char == "r":
            return "\r"
        elif char == "\\":
            return "\\"
        return char

    return re.sub(r"\\(.)", replace, text)


def parse_adc_line(line: str) -> Optional[ADCEvent]:
    line = line.strip("\r\n")
    if not line:
        return None
    parts = line.split(" ")
    if not parts or len(parts[0]) < 4:
        return None

    prefix = parts[0][0]
    cmd = parts[0][1:4]

    raw_args = parts[1:]
    unescaped_args = [adc_unescape(arg) for arg in raw_args if arg]

    sender_sid = None
    if prefix in ("B", "D", "E", "F"):
        if len(unescaped_args) > 0:
            sender_sid = unescaped_args[0]
            unescaped_args = unescaped_args[1:]

    tags = {}
    for arg in unescaped_args:
        if len(arg) >= 2 and TAG_PATTERN.match(arg[0:2]):
            tags[arg[0:2]] = arg[2:]

    return ADCEvent(
        prefix=prefix,
        cmd=cmd,
        sender_sid=sender_sid,
        args=unescaped_args,
        tags=tags,
    )


def generate_pid_and_cid() -> tuple[str, str]:
    raw_pid = os.urandom(24)
    pid_str = base64.b32encode(raw_pid).decode("utf-8").strip("=")
    hashed_bytes = tiger.hash(raw_pid)
    cid_str = base64.b32encode(hashed_bytes).decode("utf-8").strip("=")
    return pid_str, cid_str


class ADC:
    _conn: StreamConnection
    handlers: dict[str, list[EventHandler]]
    reconnect_delay: float = 5
    ping_interval: float = 30
    description_tag: Optional[str] = None
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
        port: Union[str, int] = 1511,
        socket_timeout: Optional[float] = None,
        socket_connect_timeout: Optional[float] = None,
        encoding: str = "utf-8",
    ) -> None:
        self.host = host
        self.port = int(port)
        if " " in nick:
            raise ValueError("ADC nicks cannot contain spaces")
        self.nick = nick
        self.socket_timeout = socket_timeout
        self.socket_connect_timeout = socket_connect_timeout
        self._conn = StreamConnection(
            host=self.host,
            port=self.port,
            socket_timeout=self.socket_timeout,
            socket_connect_timeout=self.socket_connect_timeout,
        )
        self.handlers = {}
        self.encoding = encoding
        self.sid: Optional[str] = None
        self.pid, self.cid = generate_pid_and_cid()
        self.features: set[str] = {"BASE", "TIGR"}
        self.hub_features: set[str] = set()
        self.client_info: dict[str, Union[str, int]] = {}

        # default handlers
        self.on("ISUP")(handlers.handle_sup)
        self.on("ISID")(handlers.handle_sid)
        self.on("IINF")(handlers.handle_inf)

    async def connect(self) -> None:
        await self._conn.connect()
        logger.info(f"Connected to ADC hub at {self.host}:{self.port}")
        # Start state machine by dynamically advertising our capabilities!
        sup_args = [f"AD{f}" for f in sorted(self.features)]
        await self.write("H", "SUP", *sup_args)

    def close(self) -> Coroutine[Any, Any, None]:
        self._conn.close()
        return self.wait_closed()

    async def wait_closed(self) -> None:
        await self._conn.wait_closed()

    async def listen(self) -> None:
        read_task = asyncio.create_task(
            self._conn.read_until(b"\n", self.max_message_size)
        )
        tasks: set[asyncio.Task[Any]] = {read_task}
        while True:
            await self._conn.drain()

            done, tasks = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

            for task in done:
                if task is read_task:
                    raw_event = await read_task
                    read_task = asyncio.create_task(
                        self._conn.read_until(b"\n", self.max_message_size)
                    )
                    tasks.add(read_task)

                    decoded = raw_event.decode(self.encoding, errors="replace")
                    logger.info(f"[{self.nick}] Received: {decoded.strip()}")
                    event = parse_adc_line(decoded)
                    if event is None:
                        continue

                    event_handlers = self.handlers.get(f"{event.prefix}{event.cmd}")
                    if not event_handlers:
                        event_handlers = self.handlers.get(
                            event.cmd, [handlers.default]
                        )
                    for handler in event_handlers:
                        handler_task = asyncio.create_task(handler(self, event))
                        tasks.add(handler_task)
                else:
                    await task

    async def ping(self) -> None:
        while True:
            await asyncio.sleep(self.ping_interval)
            await self.write("", "")

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
                for task in done:
                    await task

            except (
                OSError,
                asyncio.IncompleteReadError,
                TimeoutError,
                MessageLimitExceededError,
            ):
                logger.exception(
                    f"[{self.nick}] Retrying after {self.reconnect_delay}s"
                )
                await asyncio.sleep(self.reconnect_delay)
                await self.connect()

    async def write(self, prefix: str, cmd: str, *args: str) -> None:
        escaped_args = [adc_escape(arg) for arg in args]
        message = f"{prefix}{cmd}"
        if escaped_args:
            message += f" {' '.join(escaped_args)}"
        message += "\n"

        encoded_message = message.encode(self.encoding)
        logger.info(f"[{self.nick}] Sending: {message.strip()}")
        self._conn.write(encoded_message)
        await self._conn.drain()

    async def send_chat(self, message: str) -> None:
        if self.sid is None:
            raise ValueError("Cannot send chat message before receiving SID from hub")
        await self.write("B", "MSG", self.sid, message)

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

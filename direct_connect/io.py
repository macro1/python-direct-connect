import asyncio
from typing import Optional

from direct_connect.exceptions import MessageLimitExceededError


class StreamConnection:
    """Manages raw TCP stream lifecycles, safe delimited reads, and writes."""

    def __init__(
        self,
        host: str,
        port: int,
        socket_timeout: Optional[float] = None,
        socket_connect_timeout: Optional[float] = None,
    ) -> None:
        self.host = host
        self.port = port
        self.socket_timeout = socket_timeout
        self.socket_connect_timeout = socket_connect_timeout
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None

    async def connect(self) -> None:
        """Establishes stream connection and configures flow limits."""

        async def _connect() -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
            reader, writer = await asyncio.open_connection(
                host=self.host,
                port=self.port,
            )
            # Prioritize outgoing writes
            writer.transport.set_write_buffer_limits(0)
            return reader, writer

        self._reader, self._writer = await asyncio.wait_for(
            _connect(), timeout=self.socket_connect_timeout
        )

    def write(self, data: bytes) -> None:
        """Writes binary payload to the connection."""
        if self._writer is None:
            raise RuntimeError("Stream is not connected")
        self._writer.write(data)

    async def drain(self) -> None:
        """Drains the write buffer."""
        if self._writer is None:
            raise RuntimeError("Stream is not connected")
        await self._writer.drain()

    async def read_until(self, delimiter: bytes, max_bytes: int) -> bytes:
        """Reads safely up to max_bytes, enforcing socket timeouts."""
        reader = self._reader
        if reader is None:
            raise RuntimeError("Stream is not connected")

        async def _read() -> bytes:
            buf = bytearray()
            while True:
                char = await reader.read(1)
                if not char:
                    raise asyncio.IncompleteReadError(bytes(buf), None)
                buf.extend(char)
                if buf.endswith(delimiter):
                    return bytes(buf)
                if len(buf) >= max_bytes:
                    raise MessageLimitExceededError(
                        f"Message size exceeded limit of {max_bytes} bytes"
                    )

        if self.socket_timeout is not None:
            return await asyncio.wait_for(_read(), timeout=self.socket_timeout)
        return await _read()

    def close(self) -> None:
        """Closes the connection writer."""
        if self._writer is not None:
            self._writer.close()

    async def wait_closed(self) -> None:
        """Waits for the connection to fully close."""
        if self._writer is not None:
            await self._writer.wait_closed()

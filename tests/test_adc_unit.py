import asyncio
from unittest.mock import AsyncMock

import pytest

from direct_connect import adc
from direct_connect.adc.client import adc_unescape
from direct_connect.adc.client import parse_adc_line
from direct_connect.adc.handlers import handle_inf
from direct_connect.adc.handlers import handle_sid
from direct_connect.adc.handlers import handle_sup
from direct_connect.exceptions import MessageLimitExceededError
from direct_connect.io import StreamConnection
from direct_connect.vendored.tiger import tiger


def test_adc_unescape_all() -> None:
    assert adc_unescape("a\\nb") == "a\nb"
    assert adc_unescape("a\\rb") == "a\rb"
    assert adc_unescape("a\\\\b") == "a\\b"
    assert adc_unescape("a\\xb") == "axb"


def test_parse_adc_line_edges() -> None:
    assert parse_adc_line("") is None
    assert parse_adc_line("ABC") is None
    # No args with broadcast prefix
    event = parse_adc_line("BMSG")
    assert event is not None
    assert event.sender_sid is None


def test_send_chat_no_sid() -> None:
    client = adc.ADC()
    with pytest.raises(
        ValueError, match="Cannot send chat message before receiving SID"
    ):
        asyncio.run(client.send_chat("hello"))


def test_handlers_decorator_existing() -> None:
    client = adc.ADC()

    @client.on("TEST")
    async def h1(c: adc.ADC, ev: adc.ADCEvent) -> None:
        pass

    assert len(client.handlers["TEST"]) == 1

    @client.on("TEST")
    async def h2(c: adc.ADC, ev: adc.ADCEvent) -> None:
        pass

    assert len(client.handlers["TEST"]) == 2


@pytest.mark.asyncio
async def test_handle_sup_base_validation() -> None:
    client = adc.ADC()
    event = adc.ADCEvent(prefix="I", cmd="SUP", args=["RMBASE", "FOO"])
    with pytest.raises(ValueError, match="Hub does not support BASE protocol"):
        await handle_sup(client, event)


@pytest.mark.asyncio
async def test_handle_sid_empty() -> None:
    client = adc.ADC()
    event = adc.ADCEvent(prefix="I", cmd="SID", args=[])
    await handle_sid(client, event)
    assert client.sid is None


@pytest.mark.asyncio
async def test_handle_inf_no_sid() -> None:
    client = adc.ADC()
    event = adc.ADCEvent(prefix="I", cmd="INF")
    with pytest.raises(ValueError, match="Cannot send INF before receiving SID"):
        await handle_inf(client, event)


@pytest.mark.asyncio
async def test_handle_inf_with_description() -> None:
    import unittest.mock as mock

    client = adc.ADC()
    client.sid = "AAAB"
    client.client_info["DE"] = "My test bot"
    client.description_tag = "MyBot"
    event = adc.ADCEvent(prefix="I", cmd="INF")

    with mock.patch.object(client, "write", new_callable=AsyncMock) as mock_write:
        await handle_inf(client, event)

        # Verify that 'DEMy test bot' was sent
        written_args = mock_write.call_args[0]
        assert written_args[0] == "B"
        assert written_args[1] == "INF"
        assert "DEMy test bot" in written_args
        assert "VEMyBot" in written_args


def test_tiger_hash_padding() -> None:
    # Length of 57 bytes hits the j > 56 branch in tiger padding!
    data = b"a" * 57
    h = tiger.hash(data)
    assert len(h) == 24


@pytest.mark.asyncio
async def test_write_no_args() -> None:
    client = adc.ADC()
    client._writer = AsyncMock()
    # Call write with no additional arguments to trigger the falsy escaped_args branch
    await client.write("H", "PNG")
    assert client._writer.write.called


@pytest.mark.asyncio
async def test_listen_none_event() -> None:
    client = adc.ADC()
    # Mock stream reader to yield an empty line (which parses to None)
    reader = asyncio.StreamReader()
    reader.feed_data(b"\n")
    reader.feed_eof()
    client._reader = reader

    client._writer = AsyncMock()
    client.handlers = {}

    # Run listen loop. It should consume b"\n", parse to None, hit the continue, and raise EOF/IncompleteReadError
    with pytest.raises(asyncio.IncompleteReadError):
        await client.listen()


@pytest.mark.asyncio
async def test_ping_one() -> None:
    import unittest.mock as mock

    client = adc.ADC()
    client.ping_interval = 0.001

    with mock.patch.object(client, "write", new_callable=AsyncMock) as mock_write:
        ping_task = asyncio.create_task(client.ping())
        await asyncio.sleep(0.01)
        ping_task.cancel()
        try:
            await ping_task
        except asyncio.CancelledError:
            pass

        assert mock_write.called


@pytest.mark.asyncio
async def test_run_forever_loop_back() -> None:
    import unittest.mock as mock

    client = adc.ADC()

    count = 0

    async def mock_ping() -> None:
        nonlocal count
        count += 1
        if count > 1:
            raise ValueError("stop loop")

    async def mock_listen() -> None:
        await asyncio.sleep(0.001)

    with (
        mock.patch.object(client, "connect", new_callable=AsyncMock),
        mock.patch.object(client, "ping", side_effect=mock_ping),
        mock.patch.object(client, "listen", side_effect=mock_listen),
    ):
        with pytest.raises(ValueError, match="stop loop"):
            await client.run_forever()


@pytest.mark.asyncio
async def test_safe_readuntil_limit() -> None:
    conn = StreamConnection("localhost", 1511)
    reader = asyncio.StreamReader()
    reader.feed_data(b"A" * 100 + b"\n")
    reader.feed_eof()
    conn._reader = reader
    with pytest.raises(MessageLimitExceededError):
        await conn.read_until(b"\n", max_bytes=50)


@pytest.mark.asyncio
async def test_safe_readuntil_timeout() -> None:
    conn = StreamConnection("localhost", 1511, socket_timeout=0.01)
    reader = asyncio.StreamReader()
    conn._reader = reader
    # No data fed, so it should block and timeout
    with pytest.raises(asyncio.TimeoutError):
        await conn.read_until(b"\n", max_bytes=1000)


@pytest.mark.asyncio
async def test_safe_readuntil_normal() -> None:
    conn = StreamConnection("localhost", 1511)
    reader = asyncio.StreamReader()
    reader.feed_data(b"hello world\n")
    reader.feed_eof()
    conn._reader = reader
    res = await conn.read_until(b"\n", max_bytes=100)
    assert res == b"hello world\n"


@pytest.mark.asyncio
async def test_nmdc_safe_readuntil_limit() -> None:
    conn = StreamConnection("localhost", 411)
    reader = asyncio.StreamReader()
    reader.feed_data(b"A" * 100 + b"|")
    reader.feed_eof()
    conn._reader = reader
    with pytest.raises(MessageLimitExceededError):
        await conn.read_until(b"|", max_bytes=50)


@pytest.mark.asyncio
async def test_nmdc_safe_readuntil_timeout() -> None:
    conn = StreamConnection("localhost", 411, socket_timeout=0.01)
    reader = asyncio.StreamReader()
    conn._reader = reader
    # No data fed, so it should block and timeout
    with pytest.raises(asyncio.TimeoutError):
        await conn.read_until(b"|", max_bytes=1000)


@pytest.mark.asyncio
async def test_nmdc_safe_readuntil_normal() -> None:
    conn = StreamConnection("localhost", 411)
    reader = asyncio.StreamReader()
    reader.feed_data(b"hello world|")
    reader.feed_eof()
    conn._reader = reader
    res = await conn.read_until(b"|", max_bytes=100)
    assert res == b"hello world|"


@pytest.mark.asyncio
async def test_stream_connection_unconnected() -> None:
    conn = StreamConnection("localhost", 1511)
    with pytest.raises(RuntimeError, match="Stream is not connected"):
        conn.write(b"test")
    with pytest.raises(RuntimeError, match="Stream is not connected"):
        await conn.drain()
    with pytest.raises(RuntimeError, match="Stream is not connected"):
        await conn.read_until(b"\n", 100)

    # Safely no-op when unconnected
    conn.close()
    await conn.wait_closed()


@pytest.mark.asyncio
async def test_stream_connection_connect() -> None:
    import unittest.mock as mock
    from typing import Any

    conn = StreamConnection("localhost", 1511)

    mock_reader = AsyncMock(spec=asyncio.StreamReader)
    mock_writer = AsyncMock(spec=asyncio.StreamWriter)
    mock_writer.transport = AsyncMock()

    async def mock_open_connection(host: str, port: int) -> tuple[Any, Any]:
        return mock_reader, mock_writer

    with mock.patch(
        "asyncio.open_connection", side_effect=mock_open_connection
    ) as mock_open:
        await conn.connect()
        assert mock_open.called
        assert conn._reader is mock_reader
        assert conn._writer is mock_writer
        mock_writer.transport.set_write_buffer_limits.assert_called_with(0)

    conn.close()
    mock_writer.close.assert_called_once()

    await conn.wait_closed()
    mock_writer.wait_closed.assert_called_once()


@pytest.mark.asyncio
async def test_client_close_delegation() -> None:
    from direct_connect import nmdc

    client_adc = adc.ADC()
    client_adc._conn = AsyncMock()
    await client_adc.close()
    client_adc._conn.close.assert_called_once()
    client_adc._conn.wait_closed.assert_called_once()

    client_nmdc = nmdc.NMDC()
    client_nmdc._conn = AsyncMock()
    await client_nmdc.close()
    client_nmdc._conn.close.assert_called_once()
    client_nmdc._conn.wait_closed.assert_called_once()


@pytest.mark.asyncio
async def test_adc_run_forever_reconnect() -> None:
    import unittest.mock as mock

    client = adc.ADC()

    listen_calls = 0

    async def mock_listen() -> None:
        nonlocal listen_calls
        listen_calls += 1
        if listen_calls == 1:
            raise OSError("mock connection drop")
        else:
            raise ValueError("stop loop")

    client.reconnect_delay = 0.001

    with (
        mock.patch.object(client, "connect", new_callable=AsyncMock) as mock_connect,
        mock.patch.object(client, "listen", side_effect=mock_listen),
        mock.patch.object(client, "ping", new_callable=AsyncMock),
    ):
        with pytest.raises(ValueError, match="stop loop"):
            await client.run_forever()

        assert mock_connect.call_count == 2


@pytest.mark.asyncio
async def test_nmdc_run_forever_reconnect() -> None:
    import unittest.mock as mock

    from direct_connect import nmdc

    client = nmdc.NMDC()

    listen_calls = 0

    async def mock_listen() -> None:
        nonlocal listen_calls
        listen_calls += 1
        if listen_calls == 1:
            raise OSError("mock connection drop")
        else:
            raise ValueError("stop loop")

    client.reconnect_delay = 0.001

    with (
        mock.patch.object(client, "connect", new_callable=AsyncMock) as mock_connect,
        mock.patch.object(client, "listen", side_effect=mock_listen),
        mock.patch.object(client, "ping", new_callable=AsyncMock),
    ):
        with pytest.raises(ValueError, match="stop loop"):
            await client.run_forever()

        assert mock_connect.call_count == 2

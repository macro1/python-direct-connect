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
    assert adc_unescape("a\\sb") == "a b"


def test_parse_adc_line_edges() -> None:
    assert parse_adc_line("") is None
    assert parse_adc_line("ABC") is None
    # No args with broadcast prefix
    event = parse_adc_line("BMSG")
    assert event is not None
    assert event.sender_sid is None

    event_broadcast = parse_adc_line("BMSG AAAB hello")
    assert event_broadcast is not None
    assert event_broadcast.sender_sid == "AAAB"
    assert event_broadcast.args == ["hello"]

    event_tags = parse_adc_line("BINF AAAB ID1234 VEbot")
    assert event_tags is not None
    assert event_tags.tags == {"ID": "1234", "VE": "bot"}


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
    import unittest.mock as mock

    client = adc.ADC()
    mock_writer = mock.MagicMock(spec=asyncio.StreamWriter)
    mock_writer.drain = AsyncMock()
    client._writer = mock_writer
    # Call write with no additional arguments to trigger the falsy escaped_args branch
    await client.write("H", "PNG")
    assert mock_writer.write.called


@pytest.mark.asyncio
async def test_listen_none_event() -> None:
    import unittest.mock as mock

    client = adc.ADC()
    # Mock stream reader to yield an empty line (which parses to None)
    reader = asyncio.StreamReader()
    reader.feed_data(b"\n")
    reader.feed_eof()
    client._reader = reader

    mock_writer = mock.MagicMock(spec=asyncio.StreamWriter)
    mock_writer.drain = AsyncMock()
    client._writer = mock_writer
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

    mock_reader = mock.MagicMock(spec=asyncio.StreamReader)
    mock_writer = mock.MagicMock(spec=asyncio.StreamWriter)
    mock_writer.transport = mock.MagicMock()
    mock_writer.close = mock.MagicMock()
    mock_writer.wait_closed = AsyncMock()

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
    import unittest.mock as mock

    from direct_connect import nmdc

    client_adc = adc.ADC()
    mock_conn_adc = mock.MagicMock(spec=StreamConnection)
    mock_conn_adc.wait_closed = AsyncMock()
    client_adc._conn = mock_conn_adc
    await client_adc.close()
    mock_conn_adc.close.assert_called_once()
    mock_conn_adc.wait_closed.assert_called_once()

    client_nmdc = nmdc.NMDC()
    mock_conn_nmdc = mock.MagicMock(spec=StreamConnection)
    mock_conn_nmdc.wait_closed = AsyncMock()
    client_nmdc._conn = mock_conn_nmdc
    await client_nmdc.close()
    mock_conn_nmdc.close.assert_called_once()
    mock_conn_nmdc.wait_closed.assert_called_once()


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

    async def mock_ping() -> None:
        await asyncio.sleep(100)

    client.reconnect_delay = 0.001

    with (
        mock.patch.object(client, "connect", new_callable=AsyncMock) as mock_connect,
        mock.patch.object(client, "listen", side_effect=mock_listen),
        mock.patch.object(client, "ping", side_effect=mock_ping),
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

    async def mock_ping() -> None:
        await asyncio.sleep(100)

    client.reconnect_delay = 0.001

    with (
        mock.patch.object(client, "connect", new_callable=AsyncMock) as mock_connect,
        mock.patch.object(client, "listen", side_effect=mock_listen),
        mock.patch.object(client, "ping", side_effect=mock_ping),
    ):
        with pytest.raises(ValueError, match="stop loop"):
            await client.run_forever()

        assert mock_connect.call_count == 2


def test_adc_escape() -> None:
    from direct_connect.adc.client import adc_escape

    assert adc_escape("a b\nc\rd\\e") == "a\\sb\\nc\\rd\\\\e"


def test_adc_properties_unconnected() -> None:
    client = adc.ADC()
    with pytest.raises(RuntimeError, match="Not connected"):
        _ = client._reader
    with pytest.raises(RuntimeError, match="Not connected"):
        _ = client._writer


@pytest.mark.asyncio
async def test_adc_properties_setters() -> None:
    import unittest.mock as mock

    client = adc.ADC()
    r = mock.Mock(spec=asyncio.StreamReader)
    w = mock.Mock(spec=asyncio.StreamWriter)
    client._reader = r
    client._writer = w
    assert client._reader is r
    assert client._writer is w


@pytest.mark.asyncio
async def test_adc_connect() -> None:
    import unittest.mock as mock

    client = adc.ADC()
    client._conn = AsyncMock()
    with mock.patch.object(client, "write", new_callable=AsyncMock) as mock_write:
        await client.connect()
        client._conn.connect.assert_called_once()
        mock_write.assert_called_once_with("H", "SUP", "ADBASE", "ADTIGR")


@pytest.mark.asyncio
async def test_adc_listen_handler_dispatch() -> None:
    import unittest.mock as mock

    client = adc.ADC()
    reader = asyncio.StreamReader()
    reader.feed_data(b"ISID AAAB\n")
    reader.feed_eof()
    client._reader = reader
    mock_writer = mock.MagicMock(spec=asyncio.StreamWriter)
    mock_writer.drain = AsyncMock()
    client._writer = mock_writer

    # Run listen loop until EOF (IncompleteReadError)
    with pytest.raises(asyncio.IncompleteReadError):
        await client.listen()

    assert client.sid == "AAAB"


@pytest.mark.asyncio
async def test_adc_listen_handler_completes() -> None:
    import unittest.mock as mock

    client = adc.ADC()

    called = False

    @client.on("UNK")
    async def custom_handler(c: adc.ADC, ev: adc.ADCEvent) -> None:
        nonlocal called
        called = True

    reader = asyncio.StreamReader()
    reader.feed_data(b"IUNK AAAB\n")
    client._reader = reader
    mock_writer = mock.MagicMock(spec=asyncio.StreamWriter)
    mock_writer.drain = AsyncMock()
    client._writer = mock_writer

    listen_task = asyncio.create_task(client.listen())
    await asyncio.sleep(0.01)

    reader.feed_eof()
    with pytest.raises(asyncio.IncompleteReadError):
        await listen_task

    assert called


@pytest.mark.asyncio
async def test_adc_write_with_args() -> None:
    import unittest.mock as mock

    client = adc.ADC()
    mock_writer = mock.MagicMock(spec=asyncio.StreamWriter)
    mock_writer.drain = AsyncMock()
    client._writer = mock_writer
    client._conn._writer = client._writer
    await client.write("B", "MSG", "hello world")
    mock_writer.write.assert_called_with(b"BMSG hello\\sworld\n")


@pytest.mark.asyncio
async def test_adc_send_chat_success() -> None:
    import unittest.mock as mock

    client = adc.ADC()
    client.sid = "AAAB"
    with mock.patch.object(client, "write", new_callable=AsyncMock) as mock_write:
        await client.send_chat("hello")
        mock_write.assert_called_once_with("B", "MSG", "AAAB", "hello")


@pytest.mark.asyncio
async def test_adc_default_handler() -> None:
    from direct_connect.adc.handlers import default

    client = adc.ADC()
    event = adc.ADCEvent(prefix="I", cmd="UNK")
    await default(client, event)


@pytest.mark.asyncio
async def test_handle_sup_short_args() -> None:
    client = adc.ADC()
    event = adc.ADCEvent(prefix="I", cmd="SUP", args=["AD", "RM", "ADBASE"])
    await handle_sup(client, event)
    assert "BASE" in client.hub_features


@pytest.mark.asyncio
async def test_handle_inf_no_description() -> None:
    import unittest.mock as mock

    client = adc.ADC()
    client.sid = "AAAB"
    client.description_tag = None
    event = adc.ADCEvent(prefix="I", cmd="INF")
    with mock.patch.object(client, "write", new_callable=AsyncMock) as mock_write:
        await handle_inf(client, event)
        written_args = mock_write.call_args[0]
        assert not any(arg.startswith("VE") for arg in written_args)

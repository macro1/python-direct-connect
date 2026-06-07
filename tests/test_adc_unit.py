import asyncio
from unittest.mock import AsyncMock

import pytest

from direct_connect import adc
from direct_connect.adc.client import adc_unescape
from direct_connect.adc.client import parse_adc_line
from direct_connect.adc.handlers import handle_inf
from direct_connect.adc.handlers import handle_sid
from direct_connect.adc.handlers import handle_sup
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
    client = adc.ADC()
    client.sid = "AAAB"
    client.client_info["DE"] = "My test bot"
    client.description_tag = "MyBot"
    client.write = AsyncMock()  # type: ignore[method-assign]
    event = adc.ADCEvent(prefix="I", cmd="INF")
    await handle_inf(client, event)

    # Verify that 'DEMy test bot' was sent
    written_args = client.write.call_args[0]
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
    client = adc.ADC()
    client.ping_interval = 0.001
    client.write = AsyncMock()  # type: ignore[method-assign]

    ping_task = asyncio.create_task(client.ping())
    await asyncio.sleep(0.01)
    ping_task.cancel()
    try:
        await ping_task
    except asyncio.CancelledError:
        pass

    assert client.write.called


@pytest.mark.asyncio
async def test_run_forever_loop_back() -> None:
    client = adc.ADC()
    client.connect = AsyncMock()  # type: ignore[method-assign]

    count = 0

    async def mock_ping() -> None:
        nonlocal count
        count += 1
        if count > 1:
            raise ValueError("stop loop")

    async def mock_listen() -> None:
        await asyncio.sleep(0.001)

    client.ping = mock_ping  # type: ignore[method-assign]
    client.listen = mock_listen  # type: ignore[method-assign]

    with pytest.raises(ValueError, match="stop loop"):
        await client.run_forever()

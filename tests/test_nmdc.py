import asyncio
import logging
from unittest.mock import AsyncMock

import pytest

from direct_connect import nmdc


def test_nick_with_space_raises() -> None:
    with pytest.raises(ValueError, match="cannot contain spaces"):
        nmdc.NMDC(nick="bad nick")


@pytest.mark.asyncio
async def test_connect(
    nmdc_host_and_port: tuple[str, str], caplog: pytest.LogCaptureFixture
) -> None:
    test_nick = "mcbotter☺&️"
    test_chat = "testing?|&$ &#36; ☺️ heh"

    host, port = nmdc_host_and_port
    caplog.set_level(logging.DEBUG)
    reading_client = nmdc.NMDC(
        host=host, port=port, nick="readschat", socket_timeout=2.0
    )
    sending_client = nmdc.NMDC(host=host, port=port, nick=test_nick, socket_timeout=2.0)
    sending_client.description_comment = ""
    sending_client.description_tag = "123"
    sending_client.ping_interval = 0.1

    class SuccessError(Exception):
        pass

    @reading_client.on("message")
    async def check_message(client: nmdc.NMDC, event: nmdc.NMDCEvent) -> None:
        if event.user == test_nick and event.message == test_chat:
            raise SuccessError

    @sending_client.on("$OpList")
    async def send_message(client: nmdc.NMDC, event: nmdc.NMDCEvent) -> None:
        await sending_client.send_chat(test_chat)

    reading_chat = asyncio.create_task(reading_client.run_forever())
    sending_chat = asyncio.create_task(sending_client.run_forever())
    with pytest.raises(SuccessError):
        await asyncio.wait_for(reading_chat, 10)
    sending_chat.cancel()

    await reading_client.close()
    await sending_client.close()


def test_nmdc_decode() -> None:
    from direct_connect.nmdc.client import nmdc_decode

    assert nmdc_decode(b"a&#124;b&#36;c&amp;d", "utf-8") == "a|b$c&d"


@pytest.mark.asyncio
async def test_nmdc_properties_unconnected() -> None:
    client = nmdc.NMDC()
    with pytest.raises(RuntimeError, match="Not connected"):
        _ = client._reader
    with pytest.raises(RuntimeError, match="Not connected"):
        _ = client._writer


@pytest.mark.asyncio
async def test_nmdc_properties_setters() -> None:
    import unittest.mock as mock

    client = nmdc.NMDC()
    r = mock.Mock(spec=asyncio.StreamReader)
    w = mock.Mock(spec=asyncio.StreamWriter)
    client._reader = r
    client._writer = w
    assert client._reader is r
    assert client._writer is w


@pytest.mark.asyncio
async def test_nmdc_connect() -> None:
    client = nmdc.NMDC()
    client._conn = AsyncMock()
    await client.connect()
    client._conn.connect.assert_called_once()


@pytest.mark.asyncio
async def test_nmdc_listen_and_dispatch() -> None:
    import unittest.mock as mock

    client = nmdc.NMDC()

    events_received = []

    @client.on("message")
    async def msg_handler(c: nmdc.NMDC, ev: nmdc.NMDCEvent) -> None:
        events_received.append(ev)

    @client.on("$SomeCmd")
    async def cmd_handler(c: nmdc.NMDC, ev: nmdc.NMDCEvent) -> None:
        events_received.append(ev)

    reader = asyncio.StreamReader()
    reader.feed_data(b"<nick> hello|")
    reader.feed_data(b"$SomeCmd arg|")

    client._reader = reader
    mock_writer = mock.MagicMock(spec=asyncio.StreamWriter)
    mock_writer.drain = AsyncMock()
    client._writer = mock_writer

    listen_task = asyncio.create_task(client.listen())
    await asyncio.sleep(0.01)

    reader.feed_eof()
    with pytest.raises(asyncio.IncompleteReadError):
        await listen_task

    assert len(events_received) == 2
    assert events_received[0].event_type == "message"
    assert events_received[0].user == "nick"
    assert events_received[0].message == "hello"

    assert events_received[1].event_type == "$SomeCmd"
    assert events_received[1].message == "arg"


@pytest.mark.asyncio
async def test_nmdc_handlers() -> None:
    import unittest.mock as mock

    from direct_connect.nmdc import handlers

    client = nmdc.NMDC()
    event = nmdc.NMDCEvent(event_type="$MyCmd", message="data")
    await handlers.default(client, event)

    event_hub = nmdc.NMDCEvent(event_type="$HubName", message="My Hub")
    await handlers.store_hubname(client, event_hub)
    assert client.hub_name == "My Hub"

    client.description_comment = "my comment"
    client.description_tag = "MyTag"
    client.description_connection = "LAN"
    client.description_email = "test@example.com"
    mock_writer = mock.MagicMock(spec=asyncio.StreamWriter)
    mock_writer.drain = AsyncMock()
    client._writer = mock_writer
    client._conn._writer = client._writer

    event_lock = nmdc.NMDCEvent(event_type="$Lock", message="data")
    await handlers.connect(client, event_lock)

    written = client._writer.write.call_args_list
    assert len(written) == 2
    assert b"$Supports QuickList NoGetINFO|" in written[0][0][0]
    assert b"$MyINFO $ALL" in written[1][0][0]

    # Test connect with comments and description tags as None/empty for full branch coverage
    client2 = nmdc.NMDC()
    client2.description_comment = ""
    client2.description_tag = None
    mock_writer2 = mock.MagicMock(spec=asyncio.StreamWriter)
    mock_writer2.drain = AsyncMock()
    client2._writer = mock_writer2
    client2._conn._writer = client2._writer
    await handlers.connect(client2, event_lock)

    written2 = client2._writer.write.call_args_list
    assert len(written2) == 2
    assert b"$MyINFO $ALL" in written2[1][0][0]


@pytest.mark.asyncio
async def test_nmdc_ping() -> None:
    import unittest.mock as mock

    client = nmdc.NMDC()
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
async def test_nmdc_write_and_send_chat() -> None:
    import unittest.mock as mock

    client = nmdc.NMDC(nick="my_nick")
    mock_writer = mock.MagicMock(spec=asyncio.StreamWriter)
    mock_writer.drain = AsyncMock()
    client._writer = mock_writer
    client._conn._writer = client._writer

    await client.write("hello|world")
    mock_writer.write.assert_called_with(b"hello|world|")

    await client.send_chat("hello & welcome | test")
    mock_writer.write.assert_called_with(b"<my_nick> hello &amp; welcome &#124; test|")

import asyncio
import logging

import pytest

from direct_connect import nmdc


@pytest.mark.asyncio
async def test_connect(caplog: pytest.LogCaptureFixture) -> None:
    test_nick = "mcbotter☺&️"
    test_chat = "testing?|&$ &#36; ☺️ heh"

    caplog.set_level(logging.DEBUG)
    client = nmdc.NMDC(host="nmdc", nick=test_nick, socket_timeout=2.0)

    await client.connect()
    await client.send_chat(test_chat)
    for i in range(10):
        msg = await asyncio.wait_for(client.get_message(), 1)
        if msg == {"user": test_nick, "message": test_chat}:
            break
    else:
        pytest.fail("the expected messages were not found")

    client.close()
    await client.wait_closed()

    assert client.hub_name == "<Enter hub name here>"


@pytest.mark.asyncio
async def test_connect_with_no_description_comment(
    caplog: pytest.LogCaptureFixture,
) -> None:
    test_nick = "mcbotter☺&️2"
    test_message = f"$MyINFO $ALL {test_nick} $ $A$$0$"

    caplog.set_level(logging.DEBUG)
    client = nmdc.NMDC(host="nmdc", nick=test_nick, socket_timeout=2.0)
    client.description_comment = ""

    await client.connect()
    for i in range(10):
        msg = await asyncio.wait_for(client.get_message(), 1)
        if msg == {"user": None, "message": test_message}:
            break
    else:
        pytest.fail("the expected messages were not found")

    client.close()
    await client.wait_closed()

    assert client.hub_name == "<Enter hub name here>"


@pytest.mark.asyncio
async def test_connect_with_description_tag(caplog: pytest.LogCaptureFixture) -> None:
    test_nick = "mcbotter☺&️3"
    test_tag = "awesome client v2"
    test_message = f"$MyINFO $ALL {test_nick} bot <{test_tag}>$ $A$$0$"

    caplog.set_level(logging.DEBUG)
    client = nmdc.NMDC(host="nmdc", nick=test_nick, socket_timeout=2.0)
    client.description_tag = test_tag

    await client.connect()
    for i in range(10):
        msg = await asyncio.wait_for(client.get_message(), 1)
        if msg == {"user": None, "message": test_message}:
            break
    else:
        pytest.fail("the expected messages were not found")

    client.close()
    await client.wait_closed()

    assert client.hub_name == "<Enter hub name here>"


def test_key_from_lock() -> None:
    # some characters interfere with the DC protocol and must be escaped
    assert nmdc.client.key_from_lock(bytes([3])) == b"/%DCN096%/"

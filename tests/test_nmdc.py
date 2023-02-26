import asyncio
import logging

import pytest

from direct_connect import nmdc


@pytest.mark.asyncio
async def test_connect(caplog: pytest.LogCaptureFixture) -> None:
    test_nick = "mcbotter☺️"
    test_chat = "testing?|&$ &#36; ☺️ heh"

    caplog.set_level(logging.DEBUG)
    client = nmdc.NMDC(host="nmdc", nick=test_nick, socket_timeout=2.0)

    await client.connect()
    await client.send_chat(test_chat)
    for i in range(10):
        msg = await asyncio.wait_for(client.receive_message(), 10.0)
        print(msg)
        if msg == f"<{test_nick}> {test_chat}":
            break

    assert client.hub_name == "<Enter hub name here>"

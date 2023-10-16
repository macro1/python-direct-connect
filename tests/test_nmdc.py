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
        msg = await client.get_message()
        if msg is not None and msg == {"user": test_nick, "message": test_chat}:
            break
        await asyncio.sleep(0.1)
    else:
        raise Exception("expected message not found")

    client.close()
    await client.wait_closed()

    assert client.hub_name == "<Enter hub name here>"

import asyncio
import logging

import pytest

from direct_connect import nmdc


@pytest.mark.asyncio
async def test_connect(caplog: pytest.LogCaptureFixture) -> None:
    test_nick = "mcbotter☺️"
    test_chat = "testing?|&$ ☺️ heh"

    caplog.set_level(logging.DEBUG)
    client = nmdc.NMDC(host="nmdc", nick=test_nick, socket_timeout=2.0)

    async with asyncio.timeout(30):  # type: ignore[attr-defined]
        await client.connect()
        await asyncio.sleep(10)
        await client.send_message(test_chat)
        while True:
            msg = await client.receive_message()
            print(msg)
            if msg == f"<{test_nick}> {test_chat}":
                break

    assert client.hub_name == "<Enter hub name here>"

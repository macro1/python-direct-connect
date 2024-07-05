import asyncio
import logging

import pytest

from direct_connect import nmdc


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

    class Success(Exception):
        pass

    @reading_client.on("message")
    async def check_message(client: nmdc.NMDC, event: nmdc.NMDCEvent) -> None:
        if event.user == test_nick and event.message == test_chat:
            raise Success

    @sending_client.on("$OpList")
    async def send_message(client: nmdc.NMDC, event: nmdc.NMDCEvent) -> None:
        await sending_client.send_chat(test_chat)

    client_connect = asyncio.create_task(reading_client.connect())
    await asyncio.create_task(sending_client.connect())
    await client_connect
    reading_chat = asyncio.create_task(reading_client.run_forever())
    sending_chat = asyncio.create_task(sending_client.run_forever())
    with pytest.raises(Success):
        await asyncio.wait_for(reading_chat, 10)
    sending_chat.cancel()

    await reading_client.close()
    await sending_client.close()

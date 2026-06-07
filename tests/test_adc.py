import asyncio
import logging

import pytest

from direct_connect import adc


def test_nick_with_space_raises() -> None:
    with pytest.raises(ValueError, match="cannot contain spaces"):
        adc.ADC(nick="bad nick")


@pytest.mark.asyncio
async def test_connect(
    adc_host_and_port: tuple[str, str], caplog: pytest.LogCaptureFixture
) -> None:
    test_nick = "mcbotter"
    test_chat = "testing?|&$ &#36; ☺️ heh"

    host, port = adc_host_and_port
    caplog.set_level(logging.DEBUG)
    reading_client = adc.ADC(host=host, port=port, nick="readschat", socket_timeout=2.0)
    sending_client = adc.ADC(host=host, port=port, nick=test_nick, socket_timeout=2.0)

    class SuccessError(Exception):
        pass

    @reading_client.on("BMSG")
    async def check_message(client: adc.ADC, event: adc.ADCEvent) -> None:
        if event.args and event.args[0] == test_chat:
            raise SuccessError

    has_sent = False

    @sending_client.on("ISTA")
    async def send_message(client: adc.ADC, event: adc.ADCEvent) -> None:
        await asyncio.sleep(1)
        nonlocal has_sent
        # Trigger message only after receiving the successful login confirmation (STA 000)
        if event.args and event.args[0] == "000":
            if not has_sent:
                has_sent = True
                await sending_client.send_chat(test_chat)

    reading_chat = asyncio.create_task(reading_client.run_forever())
    sending_chat = asyncio.create_task(sending_client.run_forever())
    with pytest.raises(SuccessError):
        await asyncio.wait_for(reading_chat, 3)
    sending_chat.cancel()

    await reading_client.close()
    await sending_client.close()

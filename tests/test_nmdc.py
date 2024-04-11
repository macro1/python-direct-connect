import asyncio
import logging

import pytest

from direct_connect import nmdc
from direct_connect.nmdc.client import NMDCEvent


@pytest.mark.asyncio
async def test_connect(nmdc_host_and_port, caplog: pytest.LogCaptureFixture) -> None:
    test_nick = "mcbotter☺&️"
    test_chat = "testing?|&$ &#36; ☺️ heh"

    host, port = nmdc_host_and_port
    caplog.set_level(logging.DEBUG)
    client = nmdc.NMDC(host=host, port=port, nick="readschat", socket_timeout=2.0)
    client2 = nmdc.NMDC(host=host, port=port, nick=test_nick, socket_timeout=2.0)

    class Success(Exception):
        pass

    @client.on("message")
    async def check_message(client, event: NMDCEvent):
        print("wut", event.user, event.message)
        if event.user == test_nick and event.message == test_chat:
            raise Success

    @client2.on("$OpList")
    async def send_message(client, event):
        await client2.send_chat(test_chat)

    client_connect = asyncio.create_task(client.connect())
    await asyncio.create_task(client2.connect())
    await client_connect
    reading_chat = asyncio.create_task(client.read_forever())
    sending_chat = asyncio.create_task(client2.read_forever())
    with pytest.raises(Success):
        await asyncio.wait_for(reading_chat, 10)
    sending_chat.cancel()

    client.close()
    await client.wait_closed()
    client2.close()
    await client2.wait_closed()


#
# @pytest.mark.asyncio
# async def test_connect_with_no_description_comment(nmdc_host_and_port,
#     caplog: pytest.LogCaptureFixture,
# ) -> None:
#     test_nick = "mcbotter☺&️2"
#     test_message = f"$MyINFO $ALL {test_nick} $ $A$$0$"
#
#     host, port = nmdc_host_and_port
#     caplog.set_level(logging.DEBUG)
#     client = nmdc.NMDC(host=host, port=port, nick=test_nick, socket_timeout=2.0)
#     client.description_comment = ""
#
#     await client.connect()
#     for i in range(10):
#         msg = await asyncio.wait_for(client.get_message(), 1)
#         if msg == {"user": None, "message": test_message}:
#             break
#     else:
#         pytest.fail("the expected messages were not found")
#
#     client.close()
#     await client.wait_closed()
#
#     assert client.hub_name == "<Enter hub name here>"
#
#
# @pytest.mark.asyncio
# async def test_connect_with_description_tag(nmdc_host_and_port, caplog: pytest.LogCaptureFixture) -> None:
#     test_nick = "mcbotter☺&️3"
#     test_tag = "awesome client v2"
#     test_message = f"$MyINFO $ALL {test_nick} bot <{test_tag}>$ $A$$0$"
#
#     host, port = nmdc_host_and_port
#     caplog.set_level(logging.DEBUG)
#     client = nmdc.NMDC(host=host, port=port, nick=test_nick, socket_timeout=2.0)
#     client.description_tag = test_tag
#
#     await client.connect()
#     for i in range(10):
#         msg = await asyncio.wait_for(client.get_message(), 1)
#         if msg == {"user": None, "message": test_message}:
#             break
#     else:
#         pytest.fail("the expected messages were not found")
#
#     client.close()
#     await client.wait_closed()
#
#     assert client.hub_name == "<Enter hub name here>"
#
#
# @pytest.mark.asyncio
# async def test_disconnect():
#     nmdc_compose = DockerCompose('tests/services', compose_file_name='compose.yaml', build=True)
#     client = nmdc.NMDC(nick='disconnected', socket_timeout=2.0)
#
#     with nmdc_compose:
#         host, port = nmdc_compose.get_service_host_and_port('nmdc_disconnect', port=411)
#         client.host = host
#         client.port = port
#         await client.connect()
#     nmdc_compose.stop()
#
#     while True:
#         print('sending')
#         await asyncio.sleep(0.1)
#         await client.get_message()


@pytest.mark.asyncio
async def test_chat(nmdc_host_and_port, caplog: pytest.LogCaptureFixture):
    host, port = nmdc_host_and_port
    caplog.set_level(logging.DEBUG)
    test_message = "i am a test"

    client = nmdc.NMDC(host=host, port=port, nick="hiyabotter", socket_timeout=2.0)

    @client.on("message")
    async def respond_to_chat(client: nmdc.NMDC, event: NMDCEvent) -> None:
        await client.send_chat(test_message)

    await client.connect()
    reading = asyncio.create_task(client.read_forever())
    try:
        await asyncio.wait_for(reading, 0.1)
    except TimeoutError:
        pass

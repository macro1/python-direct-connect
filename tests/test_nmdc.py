import asyncio
import logging

import pytest

from direct_connect import nmdc


@pytest.mark.asyncio
async def test_connect(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    print("doing test")
    client = nmdc.NMDC(host="nmdc", socket_timeout=2.0)
    async with asyncio.timeout(30):  # type: ignore[attr-defined]
        await client.connect()
    assert client.hub_name == "<Enter hub name here>"

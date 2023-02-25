import asyncio

import pytest

from direct_connect import nmdc


@pytest.mark.asyncio
async def test_connect() -> None:
    print("doing test")
    client = nmdc.NMDC(host="nmdc", socket_timeout=2.0)
    async with asyncio.timeout(30):
        await client.connect()
    assert client.hub_name == "<Enter hub name here>"

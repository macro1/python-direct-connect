import asyncio
from typing import Optional
from typing import Union

from direct_connect.nmdc.connection import Connection


class NMDC:
    def __init__(
        self,
        host: str = "localhost",
        username: str = "fdsa",
        port: Union[str, int] = 411,
        socket_timeout: Optional[float] = None,
        socket_connect_timeout: Optional[float] = None,
    ):
        self.connection = Connection(
            host=host,
            username=username,
            port=port,
            socket_timeout=socket_timeout,
            socket_connect_timeout=socket_connect_timeout,
        )
        self.hub_name: Optional[str] = None

    async def connect(self) -> None:
        connect_task = asyncio.create_task(self.connection.connect())
        self.hub_name = await self.connection.get_hub_name()
        await connect_task

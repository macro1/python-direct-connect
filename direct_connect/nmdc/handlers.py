from typing import TYPE_CHECKING

from direct_connect.nmdc import logger

if TYPE_CHECKING:
    from direct_connect.nmdc.client import NMDC
    from direct_connect.nmdc.client import NMDCEvent


async def default(client: "NMDC", event: "NMDCEvent") -> None:
    logger.warning("Unhandled event", extra={"event": event})


async def store_hubname(client: "NMDC", event: "NMDCEvent") -> None:
    client.hub_name = event.message


async def connect(client: "NMDC", event: "NMDCEvent") -> None:
    await client.write("$Supports QuickList NoGetINFO")
    description = []
    if client.description_comment:
        description.append(client.description_comment)
    if client.description_tag is not None:
        description.append(f"<{client.description_tag}>")
    await client.write(
        f"$MyINFO $ALL {client.nick} {' '.join(description)}$ ${client.description_connection}1${client.description_email}$0$"
    )

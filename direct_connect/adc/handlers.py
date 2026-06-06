from typing import TYPE_CHECKING

from direct_connect.adc import logger

if TYPE_CHECKING:
    from direct_connect.adc.client import ADC
    from direct_connect.adc.client import ADCEvent


async def default(client: "ADC", event: "ADCEvent") -> None:
    logger.warning(f"Unhandled event {event}", extra={"event": event})


async def handle_sup(client: "ADC", event: "ADCEvent") -> None:
    # We already send HSUP on connect, so we don't need to do anything here
    pass


async def handle_sid(client: "ADC", event: "ADCEvent") -> None:
    if event.args:
        client.sid = event.args[0]


async def handle_inf(client: "ADC", event: "ADCEvent") -> None:
    if client.sid is None:
        raise ValueError("Cannot send INF before receiving SID from hub")
    await client.write(
        "B",
        "INF",
        client.sid,
        f"ID{client.cid}",
        f"PD{client.pid}",
        f"NI{client.nick}",
        "VEpy-direct-connect-0.1.2",
        "US1048576",
        "SL5",
        "SS1073741824",
        "CT1",
    )

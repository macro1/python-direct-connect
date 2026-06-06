from typing import TYPE_CHECKING

from direct_connect.adc import logger

if TYPE_CHECKING:
    from direct_connect.adc.client import ADC
    from direct_connect.adc.client import ADCEvent


async def default(client: "ADC", event: "ADCEvent") -> None:
    logger.warning(f"Unhandled event {event}", extra={"event": event})


async def handle_sup(client: "ADC", event: "ADCEvent") -> None:
    added, removed = set(), set()
    for arg in event.args:
        if arg.startswith("AD") and len(arg) > 2:
            added.add(arg[2:])
        elif arg.startswith("RM") and len(arg) > 2:
            removed.add(arg[2:])
    client.hub_features.update(added)
    client.hub_features.difference_update(removed)

    if "BASE" not in client.hub_features:
        raise ValueError("Hub does not support BASE protocol")


async def handle_sid(client: "ADC", event: "ADCEvent") -> None:
    if event.args:
        client.sid = event.args[0]


async def handle_inf(client: "ADC", event: "ADCEvent") -> None:
    if client.sid is None:
        raise ValueError("Cannot send INF before receiving SID from hub")
    su_value = ",".join(sorted(client.features))
    await client.write(
        "B",
        "INF",
        client.sid,
        f"ID{client.cid}",
        f"PD{client.pid}",
        f"NI{client.nick}",
        f"SU{su_value}",
        "VEpy-direct-connect-0.1.2",
        "US1048576",
        "SL5",
        "SS1073741824",
        "CT1",
    )

import asyncio
import logging

logger = logging.getLogger(__name__)


def key_from_lock(challenge: bytes) -> bytes:
    key = []
    key.append(
        challenge[0] ^ challenge[len(challenge) - 1] ^ challenge[len(challenge) - 2] ^ 5
    )
    for i in range(1, len(challenge)):
        key.append(challenge[i] ^ challenge[i - 1])
    for i in range(0, len(challenge)):
        key[i] = ((key[i] << 4) & 240) | ((key[i] >> 4) & 15)
    response = b""
    for i in range(0, len(key)):
        if key[i] in (0, 5, 36, 96, 124, 126):
            response += b"/%%DCN%03d%%/" % (key[i],)
        else:
            response += bytes([key[i]])
    return response


class NMDCClientProtocol(asyncio.Protocol):
    def __init__(
        self, *, on_connected: asyncio.Future, on_hub_name: asyncio.Future
    ) -> None:
        self.on_connected = on_connected
        self.on_hub_name = on_hub_name

    def connection_made(self, transport: asyncio.Transport) -> None:  # type: ignore[override]
        logger.warning("Connection made")
        self.transport = transport

    def connection_lost(self, exc: Exception | None) -> None:
        logger.debug("The server closed the connection")

    def data_received(self, data: bytes) -> None:
        logger.warning(f"Data received: {data!r}")

        messages = data.split(b"|")
        for message in messages:
            if not message:
                continue
            if message[0] != ord(b"$"):
                logger.warning(f"Command should start with '$': {message!r}")
                continue
            command, *params = message.split(b" ")
            command = command[1:]
            try:
                handler = getattr(self, f"handle_{command.decode()}")
            except AttributeError:
                logger.warning(f"Command not implemented: {message!r}")
                continue
            handler(*params)

    def send_message(self, message: str) -> None:
        self.transport.write(message.encode())

    def handle_Lock(self, challenge: bytes, pk: bytes, *args: bytes) -> None:
        response = key_from_lock(challenge)
        self.transport.write(
            b"$Supports HubTopic QuickList NoHello|$Key " + response + b"|"
        )

    def handle_Supports(self, *args: bytes) -> None:
        self.transport.write(
            rb"$MyINFO $ALL wut <++ V:0.673,M:P,H:0/1/0,S:2>$ $LAN(T3)0x31$example@example.com$1234$\|"
        )
        self.on_connected.set_result(True)

    def handle_HubName(self, *hub_name: bytes) -> None:
        self.on_hub_name.set_result(b" ".join(hub_name))

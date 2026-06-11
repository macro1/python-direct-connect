# direct-connect

An async Python client library for the [Direct Connect](https://en.wikipedia.org/wiki/Direct_Connect_(protocol)) file-sharing network, supporting both the NMDC and ADC protocols.

```bash
pip install direct-connect
```

## Quickstart

Register handlers with `@client.on(...)` and run the client with `run_forever()`. Keepalive pings and automatic reconnection on failure are handled natively.

### NMDC Bot

```python
import asyncio
from direct_connect import nmdc

client = nmdc.NMDC(host="example.com", nick="my_bot")

@client.on("message")
async def on_message(client: nmdc.NMDC, event: nmdc.NMDCEvent) -> None:
    if event.message == "!hello":
        await client.send_chat(f"Hello, {event.user}!")

async def main() -> None:
    await client.run_forever()

asyncio.run(main())
```

### ADC Bot

```python
import asyncio
from direct_connect import adc

client = adc.ADC(host="example.com", nick="my_bot")

@client.on("BMSG")
async def on_broadcast(client: adc.ADC, event: adc.ADCEvent) -> None:
    print(f"Message from {event.sender_sid}: {event.args}")

async def main() -> None:
    await client.run_forever()

asyncio.run(main())
```

## Scope

This library is a pure protocol client. It manages socket connections, handshakes, keepalive pings, and message serialization/deserialization. Application concerns like routing, state tracking, and rate limiting belong in your bot framework.

---

## NMDC Reference

### Client Initialization

```python
client = nmdc.NMDC(
    host="localhost",
    nick="",
    port=411,
    socket_timeout=None,
    socket_connect_timeout=None,
    encoding="utf_8",
)
```

### Handlers

Register handlers for any NMDC command or the custom `"message"` event for public chat:

```python
@client.on("message")       # Public chat event
@client.on("$HubName")      # Command-specific handler
```

Handlers receive `(client: NMDC, event: NMDCEvent)`.

#### `NMDCEvent` Attributes
*   `event_type`: The command name or `"message"`
*   `message`: Unescaped message payload
*   `user`: Sender's nickname (available only on `"message"` events)

### Configuration

Attributes can be set directly on the client instance before running:

```python
client.ping_interval = 20          # Seconds between pings
client.reconnect_delay = 5         # Reconnection backoff in seconds
client.max_message_size = 65536    # Max incoming message size
client.description_comment = "bot" # Sent inside $MyINFO
client.description_tag = None      # Client description tag
client.description_connection = "" # Connection speed tag
client.description_email = ""      # Contact email
```

---

## ADC Reference

### Client Initialization

```python
client = adc.ADC(
    host="localhost",
    nick="",
    port=1511,
    socket_timeout=None,
    socket_connect_timeout=None,
    encoding="utf-8",
)
```

### Handlers

Register handlers for specific combinations of prefix and command (e.g., `BMSG`), or fallback to the command alone (e.g., `MSG`):

```python
@client.on("BMSG")  # Specific to broadcast message
@client.on("MSG")   # Fallback for any other MSG command prefix
```

Handlers receive `(client: ADC, event: ADCEvent)`.

#### `ADCEvent` Attributes
*   `prefix`: One of `B`, `D`, `E`, `F`, `U`
*   `cmd`: Three-letter command name (e.g., `MSG`, `INF`)
*   `sender_sid`: Session ID of the sender (if applicable)
*   `args`: Positional arguments list (unescaped)
*   `tags`: Dictionary of key-value tagged parameters (e.g., `VE`, `ID`)

### Configuration

```python
client.ping_interval = 30           # Seconds between pings
client.reconnect_delay = 5          # Reconnection backoff in seconds
client.max_message_size = 65536     # Max incoming message size
client.client_info = {}             # Custom INF fields (e.g., client.client_info["DE"] = "Desc")
client.description_tag = None       # VE field in INF message
client.features = {"BASE", "TIGR"}  # Set of supported features
```

---

## Development

```bash
uv sync
uv run pytest
```

Formatting and static analysis:
```bash
uv run ruff check .
uv run ruff format .
uv run mypy .
```

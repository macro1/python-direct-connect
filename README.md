# Direct Connect Client Library for Python

An asynchronous, lightweight Direct Connect client library for Python supporting both the Neo-Modus Direct Connect (NMDC) and Advanced Direct Connect (ADC) protocols.

## Installation & Development

### Run tests
To run the project test suite and generate a coverage report:
```commandline
uv sync
uv run coverage run -m pytest
uv run coverage report
```

### Linting & Static Analysis
Run formatting, style checks, and type analysis:
```commandline
uv run ruff check .
uv run ruff format --check .
uv run mypy .
```

## Usage

### NMDC (Neo-Modus Direct Connect)

Create an NMDC client:
```python
from direct_connect import nmdc

client = nmdc.NMDC(host="example.com", nick="my_bot", socket_timeout=2.0)
```

Register a handler for incoming chat messages. Handlers are coroutines that receive the client and an `NMDCEvent` (with `event_type`, `message`, and `user` attributes).
```python
@client.on("message")
async def on_message(client: nmdc.NMDC, event: nmdc.NMDCEvent) -> None:
    print(f"{event.user}: {event.message}")
```

You can register handlers for any specific NMDC command (e.g. `$HubName`, `$OpList`) by passing the command name. Multiple handlers per event type are supported.
```python
@client.on("$HubName")
async def on_hub_name(client: nmdc.NMDC, event: nmdc.NMDCEvent) -> None:
    print(f"Hub Name: {event.message}")
```

Send a chat message:
```python
await client.send_chat("test chat")
```

Run the client. `run_forever()` connects, sends pings, listens for events, and automatically reconnects on connection errors.
```python
await client.run_forever()
```

#### Configuration Options
The `NMDC` client can be configured with the following properties before starting:
- `description_comment` (default `"bot"`): Sent inside the `$MyINFO` payload.
- `description_tag` (default `None`): Client description tag.
- `description_connection` (default `""`): Connection speed description.
- `description_email` (default `""`): Email sent inside `$MyINFO`.
- `ping_interval` (default `20` seconds): Interval between keepalive pings.
- `reconnect_delay` (default `5` seconds): Time to wait before reconnecting on failure.
- `max_message_size` (default `65536` bytes): Maximum allowed message size before raising `MessageLimitExceededError`.


### ADC (Advanced Direct Connect)

Create an ADC client:
```python
from direct_connect import adc

client = adc.ADC(host="example.com", nick="my_bot", socket_timeout=2.0)
```

Register a handler for incoming events. Handlers are coroutines that receive the client and an `ADCEvent` (with `prefix`, `cmd`, `sender_sid`, `args`, and `tags` attributes).

You can register a handler for a specific prefix-and-command combination (e.g. `"BMSG"`):
```python
@client.on("BMSG")
async def on_bmsg(client: adc.ADC, event: adc.ADCEvent) -> None:
    # event.args contains the parsed arguments (excluding prefix and command)
    # event.tags contains the key-value pairs of any tagged parameters
    print(f"Broadcast message from {event.sender_sid}: {event.args}")
```

Or you can register a handler for just the command name (e.g. `"MSG"`), which acts as a fallback if no prefix-specific handler is registered:
```python
@client.on("MSG")
async def on_msg(client: adc.ADC, event: adc.ADCEvent) -> None:
    print(f"Message event: {event.args}")
```

Send a chat message. Note that `send_chat` requires the client to have received its Session ID (`sid`) from the hub (which occurs automatically during the initial handshake). If called before `client.sid` is assigned, it will raise a `ValueError`.
```python
await client.send_chat("test chat")
```

Run the client. `run_forever()` connects, sends keepalive pings, listens for events, and automatically reconnects on connection errors.
```python
await client.run_forever()
```

#### Configuration Options
The `ADC` client can be configured with the following properties before starting:
- `client_info` (default `{}`): Dictionary of key-value pairs (e.g., `client.client_info["DE"] = "My Description"`) sent inside the `INF` message.
- `description_tag` (default `None`): Application version or description tag (sent as `VE` inside the `INF` message).
- `ping_interval` (default `30` seconds): Interval between keepalive pings.
- `reconnect_delay` (default `5` seconds): Time to wait before reconnecting on failure.
- `max_message_size` (default `65536` bytes): Maximum allowed message size before raising `MessageLimitExceededError`.
- `features` (default `{"BASE", "TIGR"}`): Set of features advertised by the client during handshake.

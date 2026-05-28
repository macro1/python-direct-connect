# Direct Connect Client Library for Python

Run tests
```commandline
uv sync
uv run coverage run -m pytest
uv run coverage report
```

Linting is ruff and can be run locally as appropriate.


## Usage

Create a client.
```python
from direct_connect import nmdc

client = nmdc.NMDC(host="example.com", nick="my_bot", socket_timeout=2.0)
```

Register a handler for incoming chat messages. Handlers are coroutines
that receive the client and an `NMDCEvent` (with `event_type`, `message`,
and `user` attributes).
```python
@client.on("message")
async def on_message(client: nmdc.NMDC, event: nmdc.NMDCEvent) -> None:
    print(f"{event.user}: {event.message}")
```

You can register handlers for any NMDC command (e.g. `$HubName`,
`$OpList`) by passing the command name. Multiple handlers per event
type are supported.

Send a chat message.
```python
await client.send_chat("test chat")
```

Run the client. `run_forever()` connects, sends pings, listens for
events, and reconnects on connection errors.
```python
await client.run_forever()
```

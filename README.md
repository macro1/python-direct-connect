# Direct Connect Client Library for Python

Run tests
```commandline
docker compose run test
```

Linting is black/isort/mypy/flake8 and those can be run locally as appropriate.


## Usage

Import and create a client.
```python
from direct_connect import nmdc

client = nmdc.NMDC(host="example.com", nick="my_bot", socket_timeout=2.0)
```

Send a message.
```python
await msg = await client.send_chat("test chat")
```

Get a message.
```python
await msg = await client.get_message()
```
Note this is 'blocking' in the sense that messages are not being
retrieved if `get_message()` is not being awaited. It may make sense to
build a worker pattern in your application with a task continually
checking for messages.

Messages are returned as dictionaries with `user` and `message` keys.
```
>>> msg
{"user": "my_bot", "message": "test chat"}
```

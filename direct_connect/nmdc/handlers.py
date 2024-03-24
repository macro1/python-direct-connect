from direct_connect.nmdc import logger
async def default(client, event, *args):
    logger.warning("Unhandled event", extra={'event': event, 'args': args})

async def store_hubname(client, event, *args):
    client.hub_name = ' '.join(args)
async def connect(client, event):
    await client.write("$Supports QuickList NoGetINFO")
    description = []
    if client.description_comment:
        description.append(client.description_comment)
    if client.description_tag is not None:
        description.append(f"<{client.description_tag}>")
    await client.write(
        f"$MyINFO $ALL {client.nick} {' '.join(description)}$ ${client.description_connection}1${client.description_email}$0$"
    )

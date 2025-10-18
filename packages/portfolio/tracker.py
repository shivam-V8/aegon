from packages.lighter_sdk_adapter.rest import get_account_by_index
from packages.lighter_sdk_adapter.ws import account_stream

async def snapshot(client, index:int):
    return await get_account_by_index(client, index)

async def stream_account(client, on_msg):
    await account_stream(client, on_msg)

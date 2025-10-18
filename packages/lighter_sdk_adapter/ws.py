import json, websockets
from .signer import create_auth_token

async def account_stream(client, on_msg, ttl=60):
    token = await create_auth_token(client, ttl)
    url = client.url.replace("https","wss") + f"/ws/account?auth={token}"
    async with websockets.connect(url) as ws:
        async for raw in ws:
            on_msg(json.loads(raw))

async def send_batch_ws(client, tx_types, tx_infos, ttl=60):
    token = await create_auth_token(client, ttl)
    url = client.url.replace("https","wss") + f"/ws/jsonapi?auth={token}"
    payload = {"type":"jsonapi/sendtxbatch","data":{"tx_types":tx_types,"tx_infos":tx_infos}}
    async with websockets.connect(url) as ws:
        await ws.send(json.dumps(payload))
        return json.loads(await ws.recv())

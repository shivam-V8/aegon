from typing import Any, Tuple
from lighter import SignerClient
from packages.lighter_sdk_adapter.signer import sign_create_order
from packages.lighter_sdk_adapter.rest import send_tx, send_tx_batch

async def sign_all(client: SignerClient, create_orders: list[dict]) -> Tuple[list[int], list[Any]]:
    tx_types, tx_infos = [], []
    for body in create_orders:
        signed = await sign_create_order(client, body)
        tx_types.append(signed["tx_type"]); tx_infos.append(signed["tx_info"])
    return tx_types, tx_infos

async def place_bracket(client: SignerClient, create_orders: list[dict]):
    types_, infos_ = await sign_all(client, create_orders)
    return await send_tx_batch(client, types_, infos_)

async def place_single(client: SignerClient, body: dict):
    signed = await sign_create_order(client, body)
    return await send_tx(client, signed["tx_type"], signed["tx_info"])

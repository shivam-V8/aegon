from typing import Any, Optional
from lighter import SignerClient
import httpx

async def send_tx(client: SignerClient, tx_type: int, tx_info: Any):
    return await client.send_tx(tx_type, tx_info)

async def send_tx_batch(client: SignerClient, tx_types: list[int], tx_infos: list[Any]):
    return await client.send_tx_batch(tx_types, tx_infos)

async def get_account_by_index(client: SignerClient, index: int):
    # SDK helper if available:
    try:
        return await client.api.get_account(by="index", value=str(index))
    except Exception:
        pass
    # REST fallback
    async with httpx.AsyncClient(base_url=client.url, timeout=15.0) as h:
        r = await h.get("/api/v1/account", params={"by":"index","value":str(index)})
        r.raise_for_status()
        return r.json()

def _normalize_orders(obj: Any) -> list[dict]:
    if isinstance(obj, list): return obj
    if isinstance(obj, dict):
        if isinstance(obj.get("orders"), list): return obj["orders"]
        if isinstance(obj.get("openOrders"), list): return obj["openOrders"]
        acc = obj.get("account")
        if isinstance(acc, dict):
            for k in ("orders","openOrders"):
                if isinstance(acc.get(k), list): return acc[k]
    return []

async def get_open_orders_by_index(client: SignerClient, index: int,
                                   market: Optional[str]=None, limit: int=200) -> list[dict]:
    try:
        acc = await client.api.get_account(by="index", value=str(index))
        orders = _normalize_orders(acc)
    except Exception:
        async with httpx.AsyncClient(base_url=client.url, timeout=15.0) as h:
            r = await h.get("/api/v1/account", params={"by":"index","value":str(index)})
            r.raise_for_status()
            orders = _normalize_orders(r.json())

    if market:
        orders = [o for o in orders if o.get("market")==market]
    return orders[:limit]

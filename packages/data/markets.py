from typing import Optional, Tuple
from lighter import SignerClient
from packages.lighter_sdk_adapter.rest import get_orderbook, get_spread


async def fetch_orderbook(client: SignerClient, market: str, depth: int = 20) -> dict:
    return await get_orderbook(client, market, depth)


async def fetch_spread(client: SignerClient, market: str, depth: int = 20) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    return await get_spread(client, market, depth)


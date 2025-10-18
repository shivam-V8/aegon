from .orders import place_single
from packages.core.usecases.close_position import build_market_close

async def close_market(client, market: str, current_side: str, base_amount: int):
    body = build_market_close(market, current_side, base_amount)
    return await place_single(client, body)

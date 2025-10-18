from typing import Optional, List, Dict

async def fetch_open_orders(exchange, market: Optional[str] = None) -> List[Dict]:
    return await exchange.list_open_orders(market=market)

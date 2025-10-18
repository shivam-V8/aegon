from ..models.enums import ORDER_TYPE_MARKET
def build_market_close(market: str, current_side: str, base_amount: int):
    return {
        "market": market,
        "side": "SELL" if current_side=="BUY" else "BUY",
        "order_type": ORDER_TYPE_MARKET,
        "base_amount": str(base_amount),
        "client_order_index": f"close-{market}"
    }

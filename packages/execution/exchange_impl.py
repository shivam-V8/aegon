# implements ExchangePort using SDK
from typing import Any, Optional
from lighter import SignerClient
from packages.core.models.order import OrderIntent
from packages.core.models.enums import ORDER_TYPE_MARKET
from packages.core.usecases.place_bracket import build_create_orders
from packages.lighter_sdk_adapter.rest import send_tx, send_tx_batch, get_open_orders_by_index
from packages.lighter_sdk_adapter.signer import sign_create_order

class LighterExchange:
    def __init__(self, client: SignerClient, account_index: int):
        self.client = client
        self.account_index = account_index

    async def place_bracket(self, intent: OrderIntent) -> Any:
        creates = build_create_orders(intent)
        tx_types, tx_infos = [], []
        for body in creates:
            signed = await sign_create_order(self.client, body)
            tx_types.append(signed["tx_type"]); tx_infos.append(signed["tx_info"])
        return await send_tx_batch(self.client, tx_types, tx_infos)

    async def close_market(self, market: str, side: str, base_amount: str) -> Any:
        body = {
            "market": market,
            "side": "SELL" if side=="BUY" else "BUY",
            "order_type": ORDER_TYPE_MARKET,
            "base_amount": base_amount,
            "client_order_index": f"close-{market}",
        }
        signed = await sign_create_order(self.client, body)
        return await send_tx(self.client, signed["tx_type"], signed["tx_info"])

    async def cancel_all(self, market: Optional[str] = None) -> Any:
        raise NotImplementedError  # add when cancel endpoint is exposed

    async def list_open_orders(self, market: Optional[str] = None) -> list[dict]:
        return await get_open_orders_by_index(self.client, self.account_index, market=market, limit=200)

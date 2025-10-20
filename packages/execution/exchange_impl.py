# implements ExchangePort using SDK
from typing import Any, Optional
from lighter import SignerClient
from packages.core.models.order import OrderIntent
from packages.core.models.enums import ORDER_TYPE_MARKET
from packages.core.usecases.place_bracket import build_create_orders
from packages.lighter_sdk_adapter.rest import send_tx, send_tx_batch, get_open_orders_by_index
from packages.lighter_sdk_adapter import rest
from packages.lighter_sdk_adapter.signer import sign_create_order
import asyncio
import inspect

class LighterExchange:
    def __init__(self, client: SignerClient, account_index: int):
        self.client = client
        self.account_index = account_index

    async def place_bracket(self, intent: OrderIntent) -> Any:
        creates = build_create_orders(intent)
        tx_types, tx_infos, api_keys = [], [], []
        for body in creates:
            # Add market_index to each order in the bracket
            market_id = await self.resolve_market_id(intent.market)
            if market_id is None:
                raise ValueError(f"Could not resolve market ID for {intent.market}")
            body["market_index"] = market_id
            signed = await sign_create_order(self.client, body)
            tx_types.append(signed["tx_type"]); tx_infos.append(signed["tx_info"]); api_keys.append(signed["api_key_index"])
        return await send_tx_batch(self.client, tx_types, tx_infos, api_key_indices=api_keys)

    async def close_market(self, market: str, side: str, base_amount: str) -> Any:
        # Get market ID for the market
        market_id = await self.resolve_market_id(market)
        if market_id is None:
            raise ValueError(f"Could not resolve market ID for {market}")
            
        body = {
            "market": market,
            "market_index": market_id,  # Add market_index to the body
            "side": "SELL" if side=="BUY" else "BUY",
            "order_type": ORDER_TYPE_MARKET,
            "base_amount": base_amount,
            "client_order_index": int(__import__('time').time()*1000),  # Use integer for client_order_index
        }
        signed = await sign_create_order(self.client, body)
        return await send_tx(self.client, signed["tx_type"], signed["tx_info"], api_key_index=signed["api_key_index"])

    async def cancel_all(self, market: Optional[str] = None) -> Any:
        raise NotImplementedError  # add when cancel endpoint is exposed

    async def list_open_orders(self, market: Optional[str] = None) -> list[dict]:
        return await get_open_orders_by_index(self.client, self.account_index, market=market, limit=200)

    # --- Minimal helpers for market maker ---
    async def get_spread(self, market: str):
        return await rest.get_spread(self.client, market)

    async def place_limit(self, market: str, side: str, price: float, base_amount: float) -> str:
        # Get market ID for the market
        market_id = await self.resolve_market_id(market)
        if market_id is None:
            raise ValueError(f"Could not resolve market ID for {market}")
            
        body = {
            "market": market,
            "market_index": market_id,  # Add market_index to the body
            "side": side,
            "order_type": "ORDER_TYPE_LIMIT",
            "base_amount": str(base_amount),
            "price": str(price),
            "client_order_index": int(__import__('time').time()*1000),  # Use integer for client_order_index
        }
        signed = await sign_create_order(self.client, body)
        await send_tx(self.client, signed["tx_type"], signed["tx_info"], api_key_index=signed["api_key_index"])
        return body["client_order_index"]

    async def resolve_market_id(self, symbol: str):
        from packages.lighter_sdk_adapter.rest import resolve_market_id
        return await resolve_market_id(self.client, symbol)

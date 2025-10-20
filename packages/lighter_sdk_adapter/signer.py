from __future__ import annotations

import inspect
import json
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Any, Optional

from lighter import SignerClient

from .rest import get_market_meta
 
def make_signer(base_url: str, account_index: int, api_key_index: int,
                api_pk: str, eth_pk: str) -> SignerClient:
    # Mirrors lighter-python sample: local signing + API client in one
    # Note: SignerClient uses api_pk for signing, eth_pk is not used in the constructor
    return SignerClient(
        url=base_url,
        private_key=api_pk,
        api_key_index=api_key_index,
        account_index=account_index,
    )

async def create_auth_token(client: SignerClient, ttl_secs: int = 60) -> str:
    return await client.create_auth_token_with_expiry(ttl_secs)

def _to_decimal(value: Any) -> Optional[Decimal]:
    if value in (None, ""):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid numeric value {value!r}") from exc

def _scale(value: Any, scale: Decimal) -> int:
    dec_value = _to_decimal(value)
    if dec_value is None:
        return 0
    scaled = (dec_value * scale).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(scaled)

async def sign_create_order(client: SignerClient, body: dict) -> dict[str, Any]:
    # Map string order types to integer enum values
    order_type_map = {
        "ORDER_TYPE_LIMIT": client.ORDER_TYPE_LIMIT,
        "ORDER_TYPE_MARKET": client.ORDER_TYPE_MARKET,
        "ORDER_TYPE_STOP_LOSS": client.ORDER_TYPE_STOP_LOSS,
        "ORDER_TYPE_TAKE_PROFIT": client.ORDER_TYPE_TAKE_PROFIT,
        "ORDER_TYPE_STOP_LOSS_LIMIT": client.ORDER_TYPE_STOP_LOSS_LIMIT,
        "ORDER_TYPE_TAKE_PROFIT_LIMIT": client.ORDER_TYPE_TAKE_PROFIT_LIMIT,
        "ORDER_TYPE_TWAP": client.ORDER_TYPE_TWAP,
    }

    # Map string time in force to integer enum values
    time_in_force_map = {
        "ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL": client.ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL,
        "ORDER_TIME_IN_FORCE_GOOD_TILL_TIME": client.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
        "ORDER_TIME_IN_FORCE_POST_ONLY": client.ORDER_TIME_IN_FORCE_POST_ONLY,
    }

    market = body.get("market")
    meta = await get_market_meta(client, market) if market else None
    price_decimals = meta.get("price_decimals") if isinstance(meta, dict) else None
    size_decimals = meta.get("size_decimals") if isinstance(meta, dict) else None
    try:
        price_decimals = int(price_decimals) if price_decimals is not None else 0
    except (TypeError, ValueError):
        price_decimals = 0
    try:
        size_decimals = int(size_decimals) if size_decimals is not None else 0
    except (TypeError, ValueError):
        size_decimals = 0
    price_scale = Decimal(10) ** price_decimals
    size_scale = Decimal(10) ** size_decimals

    order_expiry: Optional[int] = body.get("order_expiry")
    if order_expiry is not None:
        order_expiry = int(order_expiry)

    provided_api_key = body.get("api_key_index")
    provided_nonce = body.get("nonce")
    if provided_api_key is not None and provided_nonce is not None:
        api_key_index = int(provided_api_key)
        nonce_val = int(provided_nonce)
    else:
        api_key_index, nonce_val = client.nonce_manager.next_nonce()
    switch_err = client.switch_api_key(api_key_index)
    if switch_err:
        client.nonce_manager.acknowledge_failure(api_key_index)
        raise ValueError(f"switch_api_key failed: {switch_err}")

    base_amount_raw = body.get("base_amount")
    if base_amount_raw is None:
        raise ValueError("base_amount is required for create_order")
    base_amount = _scale(base_amount_raw, size_scale)

    price_raw = body.get("price")
    price = _scale(price_raw, price_scale) if price_raw is not None else 0

    trigger_price_raw = body.get("trigger_price")
    trigger_price = _scale(trigger_price_raw, price_scale) if trigger_price_raw is not None else 0

    time_in_force_val = body.get("time_in_force", "ORDER_TIME_IN_FORCE_GOOD_TILL_TIME")
    if isinstance(time_in_force_val, int):
        tif = time_in_force_val
    else:
        tif = time_in_force_map.get(str(time_in_force_val), client.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME)

    order_type_val = body.get("order_type", "ORDER_TYPE_LIMIT")
    if isinstance(order_type_val, int):
        order_type = order_type_val
    else:
        order_type = order_type_map.get(str(order_type_val), client.ORDER_TYPE_LIMIT)

    reduce_only_raw = body.get("reduce_only", False)
    if isinstance(reduce_only_raw, str):
        reduce_only = reduce_only_raw.strip().lower() in ("1", "true", "yes", "y", "on")
    else:
        reduce_only = bool(reduce_only_raw)

    # Extract parameters from body dict and call sign_create_order with individual parameters
    result = client.sign_create_order(
        market_index=int(body.get("market_index", 0)),  # Ensure market_index is an integer
        client_order_index=int(body.get("client_order_index", "0")),  # Ensure client_order_index is an integer
        base_amount=base_amount,
        price=price,
        is_ask=body.get("side") == "SELL",
        order_type=order_type,
        time_in_force=tif,
        reduce_only=reduce_only,
        trigger_price=trigger_price,
        order_expiry=order_expiry if order_expiry is not None else client.DEFAULT_28_DAY_ORDER_EXPIRY,
        nonce=nonce_val,
    )
    if inspect.isawaitable(result):
        result = await result

    tx_info, error = result if isinstance(result, (list, tuple)) and len(result) >= 2 else (result, None)
    if error:
        client.nonce_manager.acknowledge_failure(api_key_index)
        raise ValueError(f"sign_create_order failed: {error}")
    if not isinstance(tx_info, str):
        tx_info = json.dumps(tx_info)
    return {"tx_type": client.TX_TYPE_CREATE_ORDER, "tx_info": tx_info, "api_key_index": api_key_index}

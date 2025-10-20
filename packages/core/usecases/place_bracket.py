from decimal import Decimal
from datetime import datetime

from ..models.order import OrderIntent
from ..models.enums import *

def _decimal_str(value: float) -> str:
    return format(Decimal(str(value)).normalize(), "f")

def coi(prefix: str) -> str:
    return f"{prefix}-{int(datetime.utcnow().timestamp()*1000)}"

def build_create_orders(intent: OrderIntent) -> list[dict]:
    txs: list[dict] = []

    entry = {
        "market": intent.market,
        "side": intent.side,
        "order_type": ORDER_TYPE_MARKET if intent.entry_px is None else ORDER_TYPE_LIMIT,
        "base_amount": str(intent.base_amount),
        "client_order_index": coi("e"),
        "time_in_force": intent.tif
    }
    if intent.entry_px is not None:
        entry["price"] = _decimal_str(intent.entry_px)
    txs.append(entry)

    if intent.tp_px is not None:
        txs.append({
            "market": intent.market,
            "side": "SELL" if intent.side=="BUY" else "BUY",
            "order_type": ORDER_TYPE_TAKE_PROFIT,
            "base_amount": str(intent.base_amount),
            "price": _decimal_str(intent.tp_px),
            "client_order_index": coi("tp"),
        })

    if intent.stop_px is not None:
        txs.append({
            "market": intent.market,
            "side": "SELL" if intent.side=="BUY" else "BUY",
            "order_type": ORDER_TYPE_STOP_LOSS,
            "base_amount": str(intent.base_amount),
            "price": _decimal_str(intent.stop_px),
            "client_order_index": coi("sl"),
        })

    return txs

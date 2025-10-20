from typing import Any, Callable, Awaitable
from packages.signals.models import Signal


class CopyEngine:
    def __init__(self, copy_cfg: dict, exchange: Any, equity_provider: Callable[[], Any]):
        self.copy_cfg = copy_cfg
        self.exchange = exchange
        self.equity_provider = equity_provider

    async def on_signal(self, signal: Signal, leader_cfg: dict) -> dict:
        try:
            eq = self.equity_provider()
            if isinstance(eq, Awaitable):
                eq = await eq
        except Exception:
            eq = None
        return {
            "engine": "CopyEngine",
            "handled": True,
            "leader": leader_cfg.get("name"),
            "market": signal.market,
            "side": signal.side,
            "type": signal.type,
            "equity": eq,
            "note": "stub execution (no orders placed)"
        }


import time
import asyncio
import inspect
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class MSPConfig:
    capital: float = 20.0
    order_size: float = 2.0
    spread: float = 0.003
    cooling_sec: int = 30
    profit_target: float = 0.15
    max_active_cycles: int = 3
    max_drawdown: float = 3.0
    max_consecutive_losses: int = 2
    time_based_exit_sec: int = 3600
    stop_reversion: float = 0.02


class MicroSpreadPulseBot:
    def __init__(self, exchange: Any, market: str, cfg: Optional[MSPConfig] = None):
        self.exchange = exchange
        self.market = market
        self.cfg = cfg or MSPConfig()
        self.active_cycles = 0
        self.daily_profit = 0.0
        self.last_trade_ts: Optional[float] = None
        self.consecutive_losses = 0

    def should_cool(self) -> bool:
        return bool(self.last_trade_ts and (time.time() - self.last_trade_ts) < self.cfg.cooling_sec)

    async def get_mid_px(self) -> Optional[float]:
        spread_data = await self.exchange.get_spread(self.market)
        bid, ask, spr = spread_data
        if bid is not None and ask is not None:
            return (bid + ask) / 2.0
        
        # Fallback: Use last trade price from market details
        try:
            from lighter import ApiClient, Configuration, OrderApi
            async with ApiClient(Configuration(host=self.exchange.client.url)) as api_client:
                order_api = OrderApi(api_client)
                
                # Get market ID for the symbol using the exchange method
                market_id = await self.exchange.resolve_market_id(self.market)
                if market_id is None:
                    return None
                    
                # Get market details with last trade price
                ob = await order_api.order_book_details(market_id=market_id)
                details = ob.order_book_details[0] if ob.order_book_details else None
                if details and hasattr(details, 'last_trade_price'):
                    last_price = float(details.last_trade_price)
                    return last_price
        except Exception as e:
            print(f"Error getting last trade price: {e}")
        
        return None

    def _adaptive_spread(self, recent_trades: Optional[int] = None) -> float:
        if recent_trades is None:
            return self.cfg.spread
        if recent_trades >= 5:
            return 0.002
        if recent_trades <= 1:
            return 0.005
        return self.cfg.spread

    async def pulse(self, recent_trades: Optional[int] = None) -> Optional[dict]:
        if self.active_cycles >= self.cfg.max_active_cycles:
            return None
        if self.should_cool():
            return None

        mid = await self.get_mid_px()
        if mid is None:
            return None
        spr = self._adaptive_spread(recent_trades)
        bid_px = mid * (1 - spr / 2)
        ask_px = mid * (1 + spr / 2)

        size = self.cfg.order_size
        # Place symmetric limits (no-op stubs; exchange implements)
        bid_oid = await self.exchange.place_limit(self.market, side="BUY", price=bid_px, base_amount=size)
        ask_oid = await self.exchange.place_limit(self.market, side="SELL", price=ask_px, base_amount=size)

        self.active_cycles += 1
        return {"bid": bid_oid, "ask": ask_oid, "mid": mid, "spread": spr}


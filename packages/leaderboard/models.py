from pydantic import BaseModel
from typing import Optional

class TraderStats(BaseModel):
    name: str
    l1_address: str
    account_index: Optional[int] = None
    equity_usdc: Optional[float] = None
    days_active: Optional[int] = None
    pnl_7d_pct: Optional[float] = None
    pnl_30d_pct: Optional[float] = None
    sharpe_30d: Optional[float] = None
    win_rate_pct: Optional[float] = None
    trades_7d: Optional[int] = None
    max_drawdown_30d_pct: Optional[float] = None
    avg_position_usd: Optional[float] = None

class LeaderboardSnapshot(BaseModel):
    traders: list[TraderStats]
    asof_ts: float

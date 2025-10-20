from .models import TraderStats
from typing import Iterable

def eligible(t: TraderStats, sel: dict) -> bool:
    return all([
        (t.days_active or 0) >= sel.get("min_days", 0),
        (t.equity_usdc or 0) >= sel.get("min_equity_usdc", 0),
        (t.pnl_7d_pct or 0) >= sel.get("min_pnl_7d_pct", 0),
        (t.win_rate_pct or 0) >= sel.get("min_win_rate", 0),
        (t.trades_7d or 0) >= sel.get("min_trades_7d", 0),
        (t.max_drawdown_30d_pct or 0) <= sel.get("max_drawdown_30d_pct", 100),
        (t.avg_position_usd or 0) >= sel.get("min_avg_position_usd", 0),
    ])

def sort_key(t: TraderStats, sort_by: str):
    # higher is better; invert if needed
    m = {
        "sharpe_30d": t.sharpe_30d or 0.0,
        "pnl_7d_pct": t.pnl_7d_pct or 0.0,
        "win_rate":   t.win_rate_pct or 0.0,
        "pnl_30d_pct": t.pnl_30d_pct or 0.0,
    }
    return m.get(sort_by, 0.0)

def select_leaders(traders: list[TraderStats], top_n: int, sel_cfg: dict, follow_slots: int, sort_by: str) -> list[TraderStats]:
    pool = [t for t in traders[:top_n] if eligible(t, sel_cfg)]
    pool.sort(key=lambda t: sort_key(t, sort_by), reverse=True)
    return pool[:follow_slots]

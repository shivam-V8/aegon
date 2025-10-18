def size_by_risk(equity: float, risk_pct: float, entry: float, stop: float) -> int:
    risk$ = equity * (risk_pct/100.0)
    dist = max(1e-9, abs(entry - stop))
    return max(1, int(risk$ / dist))

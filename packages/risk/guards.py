def can_open(lev: float, lev_cap: float, open_positions: int, max_concurrent: int,
             day_dd: float, dd_stop: float):
    if lev > lev_cap: return (False, "LEV_CAP")
    if open_positions >= max_concurrent: return (False, "MAX_CONCURRENT")
    if day_dd <= -dd_stop: return (False, "DAILY_STOP")
    return (True, "")

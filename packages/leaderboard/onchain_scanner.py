import asyncio, time, random
from collections import Counter, defaultdict
from typing import Iterable, List, Dict, Any, Tuple, Optional
import lighter

# ---- helpers: safe model -> dict ----
def _to_dict(x):
    if hasattr(x, "model_dump"): return x.model_dump()
    if hasattr(x, "dict"): return x.dict()
    return x

def _unixts() -> float: return time.time()

class OnchainScanner:
    """
    Walks recent blocks/txs to discover active accounts,
    then ranks them using AccountApi.pnl + Account snapshot.
    """
    def __init__(self, base_url: str, lookback_blocks: int = 200, max_accounts: int = 200, rps: float = 2.0):
        self.base_url = base_url
        self.lookback_blocks = lookback_blocks
        self.max_accounts = max_accounts
        # Simple rate limiter: at most rps requests/second
        self._min_interval = 1.0 / max(0.1, rps)
        self._last_req_ts = 0.0

    async def _client(self):
        return lighter.ApiClient(configuration=lighter.Configuration(host=self.base_url))

    async def _rate_limit(self):
        now = _unixts()
        wait = self._min_interval - (now - self._last_req_ts)
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_req_ts = _unixts()

    async def _with_backoff(self, coro_factory, *, max_tries: int = 5, base_delay: float = 0.5):
        """Run coroutine factory with exponential backoff on 429s or transient errors."""
        attempt = 0
        while True:
            try:
                await self._rate_limit()
                return await coro_factory()
            except Exception as e:
                msg = str(e)
                is_rl = "429" in msg or "Too Many Requests" in msg
                if not is_rl or attempt >= max_tries - 1:
                    raise
                # backoff with jitter
                delay = base_delay * (2 ** attempt) + random.uniform(0, 0.25)
                await asyncio.sleep(delay)
                attempt += 1

    async def _recent_accounts(self) -> List[int]:
        cli = await self._client()
        try:
            blk = lighter.BlockApi(cli)
            txapi = lighter.TransactionApi(cli)

            h = await blk.current_height()                      # {"height": ...}
            h = int(_to_dict(h).get("height", 0))

            seen: Counter[int] = Counter()
            start = max(1, h - self.lookback_blocks)
            # Walk newest -> oldest to prioritize latest activity
            for ht in range(h, start - 1, -1):
                r = await self._with_backoff(lambda: txapi.block_txs(by="block_height", value=str(ht)))
                data = _to_dict(r)
                txs = data.get("txs") or data.get("transactions") or []
                for t in txs:
                    td = _to_dict(t)
                    idx = td.get("account_index") or td.get("accountIndex") or td.get("by_account")
                    if idx is None:
                        # Some models put it under nested 'tx'
                        inner = td.get("tx") or {}
                        idx = inner.get("account_index") or inner.get("by_account")
                    if idx is not None:
                        seen[int(idx)] += 1
                if len(seen) >= self.max_accounts:
                    break

            # Return most active first
            return [idx for idx, _ in seen.most_common(self.max_accounts)]
        finally:
            await cli.close()

    async def _score_accounts(self, indices: List[int]) -> List[Dict[str, Any]]:
        cli = await self._client()
        try:
            accapi = lighter.AccountApi(cli)

            scored: List[Dict[str, Any]] = []
            # Limit how many we score to avoid rate limits
            limited = list(indices)[: self.max_accounts]
            for idx in limited:
                try:
                    # PnL endpoint: rely on SDK model fields (AccountPnL / PnLEntry)
                    pnl = await self._with_backoff(lambda: accapi.pnl(account_index=int(idx)))
                    pnl_d = _to_dict(pnl)

                    # Pull commonly-present metrics; fall back gracefully
                    seven = pnl_d.get("pnl_7d_pct") or pnl_d.get("pnl7d") or 0.0
                    thirty = pnl_d.get("pnl_30d_pct") or pnl_d.get("pnl30d") or 0.0
                    win = pnl_d.get("win_rate_pct") or pnl_d.get("winRate") or 0.0
                    trades7 = pnl_d.get("trades_7d") or pnl_d.get("trades7d") or 0
                    dd30 = pnl_d.get("max_drawdown_30d_pct") or pnl_d.get("dd30d") or 0.0
                    sharpe30 = pnl_d.get("sharpe_30d") or pnl_d.get("sharpe30d") or 0.0

                    acc = await self._with_backoff(lambda: accapi.account(by="index", value=str(idx)))
                    acc_d = _to_dict(acc).get("account", _to_dict(acc))
                    eq = float(acc_d.get("total_asset_value") or acc_d.get("collateral") or 0.0)
                    l1 = acc_d.get("l1_address") or ""

                    scored.append({
                        "account_index": idx,
                        "l1_address": l1,
                        "equity_usdc": eq,
                        "pnl_7d_pct": float(seven or 0.0),
                        "pnl_30d_pct": float(thirty or 0.0),
                        "win_rate_pct": float(win or 0.0),
                        "trades_7d": int(trades7 or 0),
                        "max_drawdown_30d_pct": float(dd30 or 0.0),
                        "sharpe_30d": float(sharpe30 or 0.0),
                    })
                except Exception:
                    # Ignore accounts with missing stats or transient errors
                    continue
            return scored
        finally:
            await cli.close()

    async def top_n(self, n: int = 3,
                    min_equity: float = 50.0,
                    min_trades7: int = 5,
                    max_dd30: float = 35.0,
                    sort_by: str = "sharpe_30d") -> List[Dict[str, Any]]:
        idxs = await self._recent_accounts()
        if not idxs:
            # Nothing seen in recent blocks; return empty early
            return []

        stats = await self._score_accounts(idxs)

        def _apply_filters(rows: List[Dict[str, Any]], relax: bool = False) -> List[Dict[str, Any]]:
            if relax:
                fmin_equity = 0.0
                fmin_trades7 = 0
                fmax_dd30 = 10_000.0
            else:
                fmin_equity = min_equity
                fmin_trades7 = min_trades7
                fmax_dd30 = max_dd30
            return [
                s for s in rows
                if float(s.get("equity_usdc", 0.0)) >= fmin_equity
                and int(s.get("trades_7d", 0)) >= fmin_trades7
                and float(s.get("max_drawdown_30d_pct", 0.0)) <= fmax_dd30
            ]

        cand: List[Dict[str, Any]]
        if stats:
            cand = _apply_filters(stats)
            if not cand:
                # Relax filters if too strict
                cand = _apply_filters(stats, relax=True)
        else:
            # Fallback: no PnL stats available; fetch basic account snapshots and rank by equity
            cli = await self._client()
            try:
                accapi = lighter.AccountApi(cli)
                basics: List[Dict[str, Any]] = []
                limited = idxs[: self.max_accounts]
                for idx in limited:
                    try:
                        acc = await self._with_backoff(lambda: accapi.account(by="index", value=str(idx)))
                        acc_d = _to_dict(acc).get("account", _to_dict(acc))
                        eq = float(acc_d.get("total_asset_value") or acc_d.get("collateral") or 0.0)
                        l1 = acc_d.get("l1_address") or ""
                        basics.append({
                            "account_index": idx,
                            "l1_address": l1,
                            "equity_usdc": eq,
                            "pnl_7d_pct": 0.0,
                            "pnl_30d_pct": 0.0,
                            "win_rate_pct": 0.0,
                            "trades_7d": 0,
                            "max_drawdown_30d_pct": 0.0,
                            "sharpe_30d": 0.0,
                        })
                    except Exception:
                        continue
                # Relaxed filters since we don't have trades metrics
                cand = _apply_filters(basics, relax=True)
            finally:
                await cli.close()

        if not cand:
            return []

        # Sort policy (fallback to equity if key missing)
        sort_key = sort_by if any(sort_by in s for s in cand) else "equity_usdc"
        cand.sort(key=lambda s: float(s.get(sort_key, 0.0)), reverse=True)
        out = cand[:n]

        # Add display names (fallback to short L1)
        for i, s in enumerate(out, 1):
            short = s["l1_address"][:6] + "…" + s["l1_address"][-4:] if s["l1_address"] else f"acct{ s['account_index'] }"
            s["name"] = f"leader{i}-{short}"
        return out

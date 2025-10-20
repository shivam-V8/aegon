import time, hashlib
from typing import Iterable, List, Dict, Any
from packages.lighter_sdk_adapter.rest import get_account_by_index
from .models import Signal

def _sig_id(leader: str, market: str, side: str, ts: float, extra: str="") -> str:
    raw = f"{leader}|{market}|{side}|{ts}|{extra}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]

def _extract_positions_shape(account_payload: Dict[str, Any]) -> List[Dict[str,Any]]:
    root = account_payload.get("account", account_payload)
    pos = root.get("positions") or root.get("openPositions") or []
    return pos if isinstance(pos, list) else []

def diff_positions(prev, curr, leader_name, idx, l1) -> List[Signal]:
    """Basic OPEN/CLOSE detection from position qty deltas."""
    out: List[Signal] = []
    prev_map = { (p.get("symbol") or p.get("market") or "?"): p for p in prev }
    now_map  = { (p.get("symbol") or p.get("market") or "?"): p for p in curr }
    markets = set(prev_map.keys()) | set(now_map.keys())
    now_ts = time.time()

    for m in markets:
        p0 = prev_map.get(m)
        p1 = now_map.get(m)
        q0 = float(p0.get("position", 0)) if p0 else 0.0
        q1 = float(p1.get("position", 0)) if p1 else 0.0

        # opened or increased
        if q1 > q0 + 1e-12:
            side = "BUY"  # net long increase
            s = Signal(
                leader=leader_name, leader_account_index=idx, leader_l1=l1,
                market=m, side=side, price=None, size=abs(q1-q0),
                type="OPEN", client_ref=_sig_id(leader_name, m, side, now_ts, "inc"),
                ts=now_ts
            )
            out.append(s)
        # reduced or closed
        elif q1 < q0 - 1e-12:
            side = "SELL"  # net reduce long (or add short close). Treat as CLOSE for follower.
            s = Signal(
                leader=leader_name, leader_account_index=idx, leader_l1=l1,
                market=m, side=side, price=None, size=abs(q0-q1),
                type="CLOSE", client_ref=_sig_id(leader_name, m, side, now_ts, "dec"),
                ts=now_ts
            )
            out.append(s)
    return out

class LeaderPoller:
    """Polls leader accounts and emits Signals from position diffs."""
    def __init__(self, client, leaders: List[dict]):
        self.client = client
        self.leaders = [l for l in leaders if l.get("enabled", True)]
        self._prev_positions: Dict[int, List[Dict[str,Any]]] = {}

    async def tick(self) -> List[Signal]:
        signals: List[Signal] = []
        for L in self.leaders:
            idx = int(L["account_index"]); l1 = L["l1_address"]; name = L["name"]
            acc = await get_account_by_index(self.client, idx)
            curr = _extract_positions_shape(acc)
            prev = self._prev_positions.get(idx, [])
            if prev:
                signals += diff_positions(prev, curr, name, idx, l1)
            self._prev_positions[idx] = curr
        return signals
class DynamicLeaderPoller:
    """
    leaders_provider() -> list[dict] of {"name","l1_address","account_index", ...}
    """
    def __init__(self, client, leaders_provider):
        self.client = client
        self.leaders_provider = leaders_provider
        self._prev_positions = {}

    async def tick(self):
        from .sources import _extract_positions_shape, diff_positions  # reuse helpers
        signals = []
        leaders = await self.leaders_provider()
        for L in leaders:
            idx = int(L["account_index"])
            l1 = L["l1_address"]; name = L["name"]
            acc = await get_account_by_index(self.client, idx)
            curr = _extract_positions_shape(acc)
            prev = self._prev_positions.get(idx, [])
            if prev:
                signals += diff_positions(prev, curr, name, idx, l1)
            self._prev_positions[idx] = curr
        return signals
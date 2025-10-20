import time, httpx
from typing import Callable
from .models import TraderStats, LeaderboardSnapshot

class LeaderboardHTTPSource:
    def __init__(self, url: str):
        self.url = url

    async def fetch(self) -> LeaderboardSnapshot:
        async with httpx.AsyncClient(timeout=10) as h:
            r = await h.get(self.url)
            r.raise_for_status()
            raw = r.json()  # expect {"traders":[{...},...]}
        traders = [TraderStats(**t) for t in raw.get("traders", [])]
        return LeaderboardSnapshot(traders=traders, asof_ts=time.time())

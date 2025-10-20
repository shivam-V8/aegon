# background loop: fetch → publish → execute → alert
import asyncio, yaml, json
from packages.config.env import load_cfg
from packages.config.constants import TESTNET_ENV, MAINNET_ENV
from packages.lighter_sdk_adapter.signer import make_signer
from packages.execution.exchange_impl import LighterExchange
from packages.signals.bus import SignalBus
from packages.signals.sources import DynamicLeaderPoller
from packages.followers.engine import CopyEngine
from packages.portfolio.tracker import snapshot
from packages.leaderboard.onchain_scanner import OnchainScanner

async def equity_provider(client, account_index:int):
    acc = await snapshot(client, account_index)
    root = acc.get("account", acc)
    return float(root.get("total_asset_value") or root.get("collateral") or 0.0)

def load_copy_cfg(path="configs/copy.yml"):
    import os
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

async def run(network="testnet"):
    env_file = MAINNET_ENV if network=="mainnet" else TESTNET_ENV
    cfg = load_cfg(env_file)
    copy_cfg = load_copy_cfg()
    poll_iv = int(copy_cfg.get("poll", {}).get("interval_sec", 5))
    refresh_sec = int(copy_cfg.get("leaderboard", {}).get("refresh_sec", 30))

    client = make_signer(cfg.base_url, cfg.account_index, cfg.api_key_index, cfg.api_pk, cfg.eth_pk)
    exchange = LighterExchange(client, cfg.account_index)

    # On-chain scanner discovers + ranks leaders
    scanner = OnchainScanner(
        cfg.base_url,
        lookback_blocks=copy_cfg.get("leaderboard", {}).get("lookback_blocks", 200),
        max_accounts=copy_cfg.get("leaderboard", {}).get("max_accounts", 100),
        rps=float(copy_cfg.get("leaderboard", {}).get("rps", 1.0)),
    )

    # Provide leaders (dynamic), refreshed periodically
    leaders_cache = []
    last_refresh = 0.0

    async def provide_leaders():
        nonlocal leaders_cache, last_refresh
        now = asyncio.get_running_loop().time()
        if now - last_refresh > refresh_sec or not leaders_cache:
            top = await scanner.top_n(
                n=int(copy_cfg["leaderboard"].get("follow_slots", 3)),
                min_equity=float(copy_cfg["leaderboard"]["selection"].get("min_equity_usdc", 50)),
                min_trades7=int(copy_cfg["leaderboard"]["selection"].get("min_trades_7d", 5)),
                max_dd30=float(copy_cfg["leaderboard"]["selection"].get("max_drawdown_30d_pct", 35)),
                sort_by=copy_cfg["leaderboard"].get("sort_by", "sharpe_30d"),
            )
            # If empty, relax constraints once with defaults to seed leaders
            if not top:
                top = await scanner.top_n(n=3, min_equity=0.0, min_trades7=0, max_dd30=10_000.0, sort_by="equity_usdc")
            # map to leader dicts expected by poller/engine
            leaders_cache = [{
                "name": t["name"],
                "l1_address": t["l1_address"],
                "account_index": int(t["account_index"]),
                "markets_allow": copy_cfg["copy_defaults"].get("markets_allow", []),
                "copy_mode": copy_cfg["copy_defaults"].get("copy_mode", "risk"),
                "copy_param": copy_cfg["copy_defaults"].get("copy_param", 0.5),
                "slippage_bps": copy_cfg["copy_defaults"].get("slippage_bps", 20),
                "max_leverage": copy_cfg["copy_defaults"].get("max_leverage", 5),
                "max_positions": copy_cfg["copy_defaults"].get("max_positions", 3),
                "enabled": True,
            } for t in top]
            last_refresh = now
            print("[leaders]", json.dumps(leaders_cache, indent=2))
        return leaders_cache

    poller = DynamicLeaderPoller(client, provide_leaders)
    bus = SignalBus()

    async def exec_handler(sig):
        leaders = await provide_leaders()
        cfg_leader = next((l for l in leaders if l["name"] == sig.leader), None)
        if not cfg_leader: return
        eq = await equity_provider(client, cfg.account_index)
        engine = CopyEngine(copy_cfg, exchange, lambda: eq)
        res = await engine.on_signal(sig, cfg_leader)
        print("[ALERT]", sig.model_dump(), "res:", str(res)[:140])

    bus.subscribe(lambda s: asyncio.create_task(exec_handler(s)))

    # main loop
    while True:
        try:
            sigs = await poller.tick()
            bus.publish_many(sigs)
        except Exception as e:
            print("copy-watch error:", e)
        await asyncio.sleep(poll_iv)

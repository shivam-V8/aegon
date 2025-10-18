import argparse, asyncio, json
from packages.config.env import load_cfg
from packages.config.constants import TESTNET_ENV, MAINNET_ENV
from packages.config.logging import setup_logging
from packages.lighter_sdk_adapter.signer import make_signer
from packages.execution.exchange_impl import LighterExchange
from packages.risk.guards import can_open
from packages.risk.brackets import build_intent
from packages.portfolio.tracker import snapshot as acct_snapshot  # <-- NEW

log = setup_logging()

def envfile(network:str)->str:
    return MAINNET_ENV if network=="mainnet" else TESTNET_ENV

async def run_place(args):
    cfg = load_cfg(envfile(args.network))
    client = make_signer(cfg.base_url, cfg.account_index, cfg.api_key_index, cfg.api_pk, cfg.eth_pk)
    ex = LighterExchange(client, cfg.account_index)
    ok, reason = can_open(args.lev, cfg.risk_lev_cap, args.open_positions, cfg.max_concurrent, 0.0, cfg.risk_daily_dd_stop)
    if not ok:
        log.warn("blocked", reason=reason); return
    intent = build_intent(args.market, args.side, args.entry, args.stop, args.tp, args.size)
    res = await ex.place_bracket(intent)
    log.info("placed", result=res)

async def run_close(args):
    cfg = load_cfg(envfile(args.network))
    client = make_signer(cfg.base_url, cfg.account_index, cfg.api_key_index, cfg.api_pk, cfg.eth_pk)
    ex = LighterExchange(client, cfg.account_index)
    res = await ex.close_market(args.market, args.current_side, str(args.size))
    print(json.dumps(res, indent=2))

async def run_open_orders(args):
    cfg = load_cfg(envfile(args.network))
    client = make_signer(cfg.base_url, cfg.account_index, cfg.api_key_index, cfg.api_pk, cfg.eth_pk)
    ex = LighterExchange(client, cfg.account_index)
    orders = await ex.list_open_orders(market=args.market)
    print(json.dumps(orders, indent=2))

# ---------- NEW: balances + open positions ----------
async def run_account(args):
    cfg = load_cfg(envfile(args.network))
    client = make_signer(cfg.base_url, cfg.account_index, cfg.api_key_index, cfg.api_pk, cfg.eth_pk)
    acc = await acct_snapshot(client, cfg.account_index)

    if args.json:
        print(json.dumps(acc, indent=2))
        return

    # Try common shapes from the API; gracefully handle variations.
    root = acc.get("account", acc)
    balances = root.get("balances", [])
    positions = root.get("positions", []) or root.get("openPositions", [])

    print("=== BALANCES ===")
    if not balances:
        print("(none)")
    else:
        for b in balances:
            asset = b.get("asset") or b.get("symbol") or "?"
            free  = b.get("free") or b.get("available") or b.get("balance") or "0"
            total = b.get("total") or b.get("balance") or free
            print(f"{asset}: free={free} total={total}")

    print("\n=== OPEN POSITIONS ===")
    if not positions:
        print("(none)")
    else:
        for p in positions:
            mkt   = p.get("market") or p.get("symbol") or "?"
            side  = p.get("side") or ("LONG" if float(p.get("qty", 0)) > 0 else "SHORT")
            qty   = p.get("qty") or p.get("size") or "0"
            entry = p.get("entry_price") or p.get("avg_entry") or "?"
            upnl  = p.get("unrealized_pnl") or p.get("uPnL") or "?"
            print(f"{mkt} | {side} | qty={qty} | entry={entry} | uPnL={upnl}")
# ---------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--network", default="testnet", choices=["testnet","mainnet"])
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("place")
    p.add_argument("--market", default="HYPE-USDC")
    p.add_argument("--side", default="BUY", choices=["BUY","SELL"])
    p.add_argument("--entry", type=float, required=False)
    p.add_argument("--stop", type=float, required=True)
    p.add_argument("--tp", type=float, required=True)
    p.add_argument("--size", type=int, required=True)
    p.add_argument("--lev", type=float, default=2.0)
    p.add_argument("--open-positions", type=int, default=0)
    p.set_defaults(func=run_place)

    c = sub.add_parser("close")
    c.add_argument("--market", required=True)
    c.add_argument("--current-side", required=True, choices=["BUY","SELL"])
    c.add_argument("--size", type=int, required=True)
    c.set_defaults(func=run_close)

    o = sub.add_parser("open-orders")
    o.add_argument("--market", required=False)
    o.set_defaults(func=run_open_orders)

    # NEW: balances + positions
    a = sub.add_parser("account")
    a.add_argument("--json", action="store_true", help="print raw JSON payload")
    a.set_defaults(func=run_account)

    args = ap.parse_args()
    if not getattr(args, "func", None):
        ap.print_help(); return
    asyncio.run(args.func(args))

if __name__ == "__main__":
    main()

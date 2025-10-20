import argparse, asyncio, json
from packages.config.env import load_cfg
from packages.config.constants import TESTNET_ENV, MAINNET_ENV
from packages.config.logging import setup_logging
from packages.lighter_sdk_adapter.signer import make_signer
from packages.execution.exchange_impl import LighterExchange
from packages.risk.guards import can_open
from packages.risk.brackets import build_intent
from packages.portfolio.tracker import snapshot as acct_snapshot
from apps.trader.tasks.signal_watch import run as run_signal_watch
from packages.strategies.micro_spread_pulse import MicroSpreadPulseBot, MSPConfig


log = setup_logging()

def envfile(network:str)->str:
    return MAINNET_ENV if network=="mainnet" else TESTNET_ENV

async def run_place(args):
    log.info("=== PLACE ORDER ===", market=args.market, side=args.side, entry=args.entry, stop=args.stop, tp=args.tp, size=args.size)
    
    log.info("Loading configuration...")
    cfg = load_cfg(envfile(args.network))
    log.info("Config loaded", base_url=cfg.base_url, account_index=cfg.account_index)
    
    log.info("Creating signer client...")
    client = make_signer(cfg.base_url, cfg.account_index, cfg.api_key_index, cfg.api_pk, cfg.eth_pk)
    log.info("Signer client created successfully")
    
    log.info("Creating exchange instance...")
    ex = LighterExchange(client, cfg.account_index)
    log.info("Exchange instance created")
    
    log.info("Checking risk guards...")
    ok, reason = can_open(args.lev, cfg.risk_lev_cap, args.open_positions, cfg.max_concurrent, 0.0, cfg.risk_daily_dd_stop)
    if not ok:
        log.warn("Risk guard blocked order", reason=reason)
        return
    
    log.info("Building order intent...")
    intent = build_intent(args.market, args.side, args.entry, args.stop, args.tp, args.size)
    log.info("Order intent built", intent=intent.model_dump())
    
    log.info("Placing bracket order...")
    res = await ex.place_bracket(intent)
    log.info("Bracket order placed successfully", result=res)

async def run_close(args):
    log.info("=== CLOSE POSITION ===", market=args.market, current_side=args.current_side, size=args.size)
    
    log.info("Loading configuration...")
    cfg = load_cfg(envfile(args.network))
    log.info("Config loaded", base_url=cfg.base_url, account_index=cfg.account_index)
    
    log.info("Creating signer client...")
    client = make_signer(cfg.base_url, cfg.account_index, cfg.api_key_index, cfg.api_pk, cfg.eth_pk)
    log.info("Signer client created successfully")
    
    log.info("Creating exchange instance...")
    ex = LighterExchange(client, cfg.account_index)
    log.info("Exchange instance created")
    
    log.info("Closing market position...")
    res = await ex.close_market(args.market, args.current_side, str(args.size))
    log.info("Position closed successfully", result=res)
    print(json.dumps(res, indent=2))

async def run_open_orders(args):
    log.info("=== LIST OPEN ORDERS ===", market=args.market or "ALL")
    
    log.info("Loading configuration...")
    cfg = load_cfg(envfile(args.network))
    log.info("Config loaded", base_url=cfg.base_url, account_index=cfg.account_index)
    
    log.info("Creating signer client...")
    client = make_signer(cfg.base_url, cfg.account_index, cfg.api_key_index, cfg.api_pk, cfg.eth_pk)
    log.info("Signer client created successfully")
    
    log.info("Creating exchange instance...")
    ex = LighterExchange(client, cfg.account_index)
    log.info("Exchange instance created")
    
    log.info("Fetching open orders...")
    orders = await ex.list_open_orders(market=args.market)
    log.info("Open orders fetched", count=len(orders))
    print(json.dumps(orders, indent=2))

# ---------- NEW: balances + open positions ----------
async def run_account(args):
    log.info("=== ACCOUNT SNAPSHOT ===")
    
    log.info("Loading configuration...")
    cfg = load_cfg(envfile(args.network))
    log.info("Config loaded", base_url=cfg.base_url, account_index=cfg.account_index)
    
    log.info("Creating signer client...")
    client = make_signer(cfg.base_url, cfg.account_index, cfg.api_key_index, cfg.api_pk, cfg.eth_pk)
    log.info("Signer client created successfully")
    
    log.info("Fetching account snapshot...")
    acc = await acct_snapshot(client, cfg.account_index)
    log.info("Account snapshot fetched")

    if args.json:
        log.info("Returning raw JSON payload")
        print(json.dumps(acc, indent=2))
        return

    # Try common shapes from the API; gracefully handle variations.
    root = acc.get("account", acc)
    balances = root.get("balances", [])
    positions = root.get("positions", []) or root.get("openPositions", [])

    log.info("Processing account data", balances_count=len(balances), positions_count=len(positions))

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

    cw = sub.add_parser("copy-watch")
    cw.set_defaults(func=lambda args: asyncio.run(run_signal_watch(args.network)))

    # market maker: micro-spread pulse
    mm = sub.add_parser("mm")
    mm.add_argument("--market", required=True)
    mm.add_argument("--order-size", type=float, default=2.0)
    mm.add_argument("--spread", type=float, default=0.003)
    mm.add_argument("--cooling", type=int, default=30)
    mm.add_argument("--max-cycles", type=int, default=3)
    mm.set_defaults(func=run_mm)

    # NEW: test command for individual components
    test = sub.add_parser("test")
    test.add_argument("--function", required=True, choices=["config", "signer", "exchange", "account", "orders"])
    test.set_defaults(func=run_test)

    # NEW: market data command for live prices and order books
    md = sub.add_parser("market-data")
    md.add_argument("--market", required=True, help="Market symbol (e.g., BTC, ETH, SOL)")
    md.add_argument("--depth", type=int, default=10, help="Order book depth (0 for spread only)")
    md.set_defaults(func=run_market_data)

    # NEW: list all markets with live prices
    lm = sub.add_parser("list-markets")
    lm.add_argument("--limit", type=int, default=20, help="Number of markets to show")
    lm.set_defaults(func=run_list_markets)

    args = ap.parse_args()
    if not getattr(args, "func", None):
        ap.print_help(); return
    asyncio.run(args.func(args))

async def run_mm(args):
    log.info("=== MARKET MAKER START ===", market=args.market, order_size=args.order_size, spread=args.spread, cooling=args.cooling, max_cycles=args.max_cycles)
    
    log.info("Loading configuration...")
    cfg = load_cfg(envfile(args.network))
    log.info("Config loaded", base_url=cfg.base_url, account_index=cfg.account_index)
    
    log.info("Creating signer client...")
    client = make_signer(cfg.base_url, cfg.account_index, cfg.api_key_index, cfg.api_pk, cfg.eth_pk)
    log.info("Signer client created successfully")
    
    log.info("Creating exchange instance...")
    ex = LighterExchange(client, cfg.account_index)
    log.info("Exchange instance created")
    
    log.info("Creating market maker bot...")
    bot = MicroSpreadPulseBot(ex, args.market, MSPConfig(
        capital=20.0,
        order_size=args.order_size,
        spread=args.spread,
        cooling_sec=args.cooling,
        max_active_cycles=args.max_cycles,
    ))
    log.info("Market maker bot created")
    
    log.info("Starting market maker loop...")
    while True:
        try:
            log.info("Running market maker pulse...")
            res = await bot.pulse()
            if res:
                log.info("Pulse completed", **res)
            else:
                log.info("Pulse completed with no result")
        except Exception as e:
            log.warn("Market maker error", err=str(e))
        log.info("Waiting for next pulse", sleep_sec=args.cooling)
        await asyncio.sleep(args.cooling)

async def run_market_data(args):
    log.info("=== MARKET DATA FETCH ===", market=args.market, depth=args.depth)
    
    log.info("Loading configuration...")
    cfg = load_cfg(envfile(args.network))
    log.info("Config loaded", base_url=cfg.base_url)
    
    log.info("Creating signer client...")
    client = make_signer(cfg.base_url, cfg.account_index, cfg.api_key_index, cfg.api_pk, cfg.eth_pk)
    log.info("Signer client created successfully")
    
    log.info("Creating exchange instance...")
    ex = LighterExchange(client, cfg.account_index)
    log.info("Exchange instance created")
    
    try:
        log.info("Fetching spread data...")
        best_bid, best_ask, spread = await ex.get_spread(args.market)
        log.info("Spread data fetched", best_bid=best_bid, best_ask=best_ask, spread=spread)
        
        if best_bid is not None and best_ask is not None:
            mid_price = (best_bid + best_ask) / 2
            spread_pct = (spread / mid_price * 100) if spread else 0
            
            print(f"\n=== {args.market.upper()} MARKET DATA ===")
            print(f"Best Bid:  ${best_bid:.6f}")
            print(f"Best Ask:  ${best_ask:.6f}")
            print(f"Mid Price: ${mid_price:.6f}")
            print(f"Spread:    ${spread:.6f} ({spread_pct:.4f}%)")
            
            if args.depth > 0:
                log.info("Fetching order book...")
                from packages.lighter_sdk_adapter.rest import get_orderbook
                orderbook = await get_orderbook(client, args.market, args.depth)
                log.info("Order book fetched", bids_count=len(orderbook["bids"]), asks_count=len(orderbook["asks"]))
                
                print(f"\n=== ORDER BOOK (Top {args.depth}) ===")
                print("BIDS:")
                for i, (price, size) in enumerate(orderbook["bids"][:args.depth]):
                    print(f"  {i+1:2d}. ${price:>10.6f} | {size:>12.6f}")
                
                print("\nASKS:")
                for i, (price, size) in enumerate(orderbook["asks"][:args.depth]):
                    print(f"  {i+1:2d}. ${price:>10.6f} | {size:>12.6f}")
        else:
            log.warning("No price data available", market=args.market)
            print(f"No price data available for {args.market}")
            
    except Exception as e:
        log.error("Error fetching market data", error=str(e))
        print(f"Error fetching market data: {e}")

async def run_list_markets(args):
    log.info("=== LIST ALL MARKETS ===", limit=args.limit)
    
    log.info("Loading configuration...")
    cfg = load_cfg(envfile(args.network))
    log.info("Config loaded", base_url=cfg.base_url)
    
    log.info("Creating signer client...")
    client = make_signer(cfg.base_url, cfg.account_index, cfg.api_key_index, cfg.api_pk, cfg.eth_pk)
    log.info("Signer client created successfully")
    
    try:
        # Get market metadata from the SDK
        from lighter import ApiClient, Configuration, OrderApi
        async with ApiClient(Configuration(host=cfg.base_url)) as cli:
            api = OrderApi(cli)
            
            ob = await api.order_books()
            
            # Access the order_books directly from the object
            rows = ob.order_books
            
            log.info("Markets fetched", count=len(rows))
            
            print(f"\n=== AVAILABLE MARKETS (showing {args.limit} of {len(rows)}) ===")
            print(f"{'Market':<12} {'Market ID':<10} {'Status':<10} {'Min Size':<12} {'Taker Fee':<10}")
            print("-" * 70)
            
            count = 0
            for row in rows[:args.limit]:
                # Access attributes directly from the object
                symbol = getattr(row, 'symbol', 'N/A')
                market_id = getattr(row, 'market_id', 'N/A')
                status = getattr(row, 'status', 'N/A')
                min_size = getattr(row, 'min_base_amount', 'N/A')
                taker_fee = getattr(row, 'taker_fee', 'N/A')
                
                print(f"{symbol:<12} {market_id:<10} {status:<10} {min_size:<12} {taker_fee:<10}")
                count += 1
                    
            print(f"\nShowing {count} markets (total: {len(rows)})")
    except Exception as e:
        log.error("Error listing markets", error=str(e))
        print(f"Error listing markets: {e}")

async def run_test(args):
    log.info("=== TEST FUNCTION ===", function=args.function)
    
    if args.function == "config":
        log.info("Testing configuration loading...")
        cfg = load_cfg(envfile(args.network))
        log.info("Config test passed", base_url=cfg.base_url, account_index=cfg.account_index)
        
    elif args.function == "signer":
        log.info("Testing signer client creation...")
        cfg = load_cfg(envfile(args.network))
        client = make_signer(cfg.base_url, cfg.account_index, cfg.api_key_index, cfg.api_pk, cfg.eth_pk)
        log.info("Signer test passed")
        
    elif args.function == "exchange":
        log.info("Testing exchange instance creation...")
        cfg = load_cfg(envfile(args.network))
        client = make_signer(cfg.base_url, cfg.account_index, cfg.api_key_index, cfg.api_pk, cfg.eth_pk)
        ex = LighterExchange(client, cfg.account_index)
        log.info("Exchange test passed")
        
    elif args.function == "account":
        log.info("Testing account snapshot...")
        cfg = load_cfg(envfile(args.network))
        client = make_signer(cfg.base_url, cfg.account_index, cfg.api_key_index, cfg.api_pk, cfg.eth_pk)
        acc = await acct_snapshot(client, cfg.account_index)
        log.info("Account test passed", keys=list(acc.keys())[:5])
        
    elif args.function == "orders":
        log.info("Testing open orders fetch...")
        cfg = load_cfg(envfile(args.network))
        client = make_signer(cfg.base_url, cfg.account_index, cfg.api_key_index, cfg.api_pk, cfg.eth_pk)
        ex = LighterExchange(client, cfg.account_index)
        orders = await ex.list_open_orders()
        log.info("Orders test passed", count=len(orders))
        
    else:
        log.error("Unknown test function", function=args.function)

if __name__ == "__main__":
    main()

from typing import Any, Optional, List, Tuple, Dict, Union
from lighter import SignerClient
import lighter
import httpx
import asyncio

async def send_tx(client: SignerClient, tx_type: int, tx_info: Any, api_key_index: Optional[int] = None):
    try:
        return await client.send_tx(tx_type, tx_info)
    except Exception:
        if api_key_index is not None:
            client.nonce_manager.acknowledge_failure(api_key_index)
        raise

async def send_tx_batch(client: SignerClient, tx_types: list[int], tx_infos: list[Any], api_key_indices: Optional[List[int]] = None):
    try:
        return await client.send_tx_batch(tx_types, tx_infos)
    except Exception:
        if api_key_indices:
            for idx in api_key_indices:
                client.nonce_manager.acknowledge_failure(idx)
        raise

async def get_account_by_index(client: SignerClient, index: int):
    # SDK helper if available:
    try:
        return await client.api.get_account(by="index", value=str(index))
    except Exception:
        pass
    # REST fallback
    async with httpx.AsyncClient(base_url=client.url, timeout=15.0) as h:
        r = await h.get("/api/v1/account", params={"by":"index","value":str(index)})
        r.raise_for_status()
        return r.json()

def _normalize_orders(obj: Any) -> list[dict]:
    if isinstance(obj, list): return obj
    if isinstance(obj, dict):
        if isinstance(obj.get("orders"), list): return obj["orders"]
        if isinstance(obj.get("openOrders"), list): return obj["openOrders"]
        acc = obj.get("account")
        if isinstance(acc, dict):
            for k in ("orders","openOrders"):
                if isinstance(acc.get(k), list): return acc[k]
    return []

async def get_open_orders_by_index(client: SignerClient, index: int,
                                   market: Optional[str]=None, limit: int=200) -> list[dict]:
    try:
        acc = await client.api.get_account(by="index", value=str(index))
        orders = _normalize_orders(acc)
    except Exception:
        async with httpx.AsyncClient(base_url=client.url, timeout=15.0) as h:
            r = await h.get("/api/v1/account", params={"by":"index","value":str(index)})
            r.raise_for_status()
            orders = _normalize_orders(r.json())

    if market:
        orders = [o for o in orders if o.get("market")==market]
    return orders[:limit]

_MARKET_ID_CACHE: Dict[str, int] = {}
_MARKET_META_CACHE: Dict[str, Dict[str, Any]] = {}

def _norm_symbol(sym: str) -> str:
    s = (sym or "").upper()
    # Remove common separators to normalize (ETH-USDC, ETH/USDC, ETHUSDC → ETHUSDC)
    for ch in ("-", "/", ":", "_"):
        s = s.replace(ch, "")
    return s

def _maybe_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

def _maybe_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    if isinstance(value, float):
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def _cache_market_entry(data: Any) -> None:
    if not isinstance(data, dict):
        return
    sym_raw = data.get("symbol") or data.get("market") or data.get("name")
    if not sym_raw:
        return
    ns = _norm_symbol(sym_raw)
    market_id = _maybe_int(data.get("market_id") or data.get("marketId") or data.get("id"))
    if market_id is not None:
        _MARKET_ID_CACHE[ns] = market_id
    meta = _MARKET_META_CACHE.get(ns, {}).copy()
    if market_id is not None:
        meta["market_id"] = market_id
    meta["symbol"] = sym_raw
    for meta_key, source_keys in (
        ("price_decimals", ("supported_price_decimals", "price_decimals")),
        ("size_decimals", ("supported_size_decimals", "size_decimals")),
        ("quote_decimals", ("supported_quote_decimals", "quote_decimals")),
        ("quote_multiplier", ("quote_multiplier", "quoteMultiplier")),
    ):
        if meta_key not in meta or meta[meta_key] is None:
            for sk in source_keys:
                val = _maybe_int(data.get(sk))
                if val is not None:
                    meta[meta_key] = val
                    break
    for meta_key, source_keys in (
        ("min_base_amount", ("min_base_amount", "minBaseAmount")),
        ("min_quote_amount", ("min_quote_amount", "minQuoteAmount")),
    ):
        if meta_key not in meta or meta[meta_key] is None:
            for sk in source_keys:
                val = _maybe_float(data.get(sk))
                if val is not None:
                    meta[meta_key] = val
                    break
    _MARKET_META_CACHE[ns] = meta

async def resolve_market_id(client: SignerClient, symbol: str) -> Optional[int]:
    """Resolve market_id for a human symbol using OrderApi.order_books(), with in-memory cache."""
    key = _norm_symbol(symbol)
    if key in _MARKET_ID_CACHE:
        return _MARKET_ID_CACHE[key]

    async with lighter.ApiClient(configuration=lighter.Configuration(host=client.url)) as api_client:
        order_api = lighter.OrderApi(api_client)
        # First try SDK order_books()
        try:
            books = await order_api.order_books()
            # Attempt to extract iterable from possible SDK model shapes
            sym_map: Dict[str, int] = {}
            def to_dict(x):
                if hasattr(x, "model_dump"): return x.model_dump()
                if hasattr(x, "dict"): return x.dict()
                return getattr(x, "__dict__", {})
            buckets = []
            bd = to_dict(books)
            for k in ("order_books", "data", "books", "items"):
                v = bd.get(k)
                if isinstance(v, list): buckets = v; break
            if not buckets and isinstance(books, list):
                buckets = books
            # Flatten potential nested containers
            for row in buckets or []:
                d = to_dict(row)
                market_id = d.get("market_id") or d.get("marketId")
                sym = d.get("symbol") or d.get("market") or d.get("name") or ""
                # Sometimes nested under 'market' or 'info'
                if market_id is None:
                    for nk in ("market", "info", "details"):
                        if isinstance(d.get(nk), dict):
                            md = d[nk]
                            market_id = md.get("market_id") or md.get("marketId")
                            sym = sym or md.get("symbol") or md.get("market") or md.get("name") or ""
                            _cache_market_entry(md)
                if market_id is not None:
                    ns = _norm_symbol(sym)
                    if ns:
                        mid = int(market_id)
                        _MARKET_ID_CACHE[ns] = mid
                        sym_map[ns] = mid
                        _cache_market_entry(d)

            # Direct hit after population
            if key in _MARKET_ID_CACHE:
                return _MARKET_ID_CACHE[key]

            # Heuristics: bare base like "ETH" → prefer ETHUSDC, else any containing base
            if 2 <= len(key) <= 5 and sym_map:
                for quote in ("USDC", "USD", "USDT"):
                    cand = _norm_symbol(key + quote)
                    if cand in sym_map:
                        _MARKET_ID_CACHE[key] = sym_map[cand]
                        return sym_map[cand]
                for ns, mid in sym_map.items():
                    if ns.endswith("USDC") and ns.startswith(key):
                        _MARKET_ID_CACHE[key] = mid
                        return mid
                for ns, mid in sym_map.items():
                    if key in ns:
                        _MARKET_ID_CACHE[key] = mid
                        return mid
        except Exception:
            pass

    # REST fallbacks: exchangeStats and orderBooks (plural)
    async with httpx.AsyncClient(base_url=client.url, timeout=15.0) as h:
        # exchangeStats
        try:
            r = await h.get("/api/v1/exchangeStats")
            r.raise_for_status()
            data = r.json()
            if isinstance(data, list):
                for it in data:
                    sym = (it.get("symbol") or it.get("market") or it.get("name") or "").upper()
                    mid = it.get("market_id") or it.get("marketId") or it.get("id")
                    if sym and mid is not None:
                        ns = _norm_symbol(sym)
                        _MARKET_ID_CACHE[ns] = int(mid)
                        _cache_market_entry(it)
            if key in _MARKET_ID_CACHE:
                return _MARKET_ID_CACHE[key]
        except Exception:
            pass

        # orderBooks
        try:
            r = await h.get("/api/v1/orderBooks")
            r.raise_for_status()
            data = r.json()
            rows = data.get("order_books") if isinstance(data, dict) else (data if isinstance(data, list) else [])
            for it in rows:
                if isinstance(it, dict):
                    sym = (it.get("symbol") or it.get("market") or it.get("name") or "").upper()
                    mid = it.get("market_id") or it.get("marketId") or it.get("id")
                    if sym and mid is not None:
                        ns = _norm_symbol(sym)
                        _MARKET_ID_CACHE[ns] = int(mid)
                        _cache_market_entry(it)
            return _MARKET_ID_CACHE.get(key)
        except Exception:
            return _MARKET_ID_CACHE.get(key)

async def get_market_meta(client: SignerClient, symbol: str) -> Optional[Dict[str, Any]]:
    key = _norm_symbol(symbol)
    if key in _MARKET_META_CACHE:
        return _MARKET_META_CACHE[key]

    market_id = await resolve_market_id(client, symbol)
    if market_id is None:
        return None

    async with lighter.ApiClient(configuration=lighter.Configuration(host=client.url)) as api_client:
        order_api = lighter.OrderApi(api_client)
        try:
            resp = await order_api.order_book_details(market_id=market_id)
        except Exception:
            resp = None
        details = []
        if resp is not None:
            detail_obj = getattr(resp, "order_book_details", None)
            if isinstance(detail_obj, list):
                details = detail_obj
            elif detail_obj:
                details = [detail_obj]
        for detail in details:
            if hasattr(detail, "model_dump"):
                data = detail.model_dump()
            elif hasattr(detail, "dict"):
                data = detail.dict()
            else:
                data = getattr(detail, "__dict__", {}) or detail
            if isinstance(data, dict):
                _cache_market_entry(data)
                ns = _norm_symbol(data.get("symbol") or data.get("market") or data.get("name") or symbol)
                if ns in _MARKET_META_CACHE:
                    return _MARKET_META_CACHE[ns]
    return _MARKET_META_CACHE.get(key)

# ------------------- Orderbook helpers (SDK via market_id) -------------------
async def get_orderbook(client: SignerClient, symbol: str, depth: int = 20) -> dict:
    """Fetch orderbook for a symbol via SDK OrderApi using market_id. Returns {bids, asks}."""
    market_id = await resolve_market_id(client, symbol)
    if market_id is None:
        raise ValueError(f"Unknown market symbol: {symbol}")

    async with lighter.ApiClient(configuration=lighter.Configuration(host=client.url)) as api_client:
        order_api = lighter.OrderApi(api_client)
        ob = await order_api.order_book_details(market_id=market_id)
    
    d = ob.model_dump() if hasattr(ob, "model_dump") else (ob.dict() if hasattr(ob, "dict") else getattr(ob, "__dict__", {}))
    bids = d.get("bids") or d.get("buy") or []
    asks = d.get("asks") or d.get("sell") or []
    return {"bids": bids, "asks": asks}

def _best_px(levels: Union[List[List[float]], List[dict]], side: str) -> Optional[float]:
    if not levels:
        return None
    # Support [[px,qty], ...] or [{"price":..., "qty":...}, ...]
    def _px(x):
        if isinstance(x, dict):
            return float(x.get("price") or x.get("px") or 0.0)
        return float(x[0])
    try:
        if side == "bid":
            return max(_px(x) for x in levels)
        return min(_px(x) for x in levels)
    except Exception:
        return None

async def get_spread(client: SignerClient, market: str, depth: int = 20) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Return (best_bid, best_ask, spread) where spread = ask - bid."""
    ob_result = get_orderbook(client, market, depth=depth)
    if asyncio.iscoroutine(ob_result):
        ob = await ob_result
    else:
        ob = ob_result
    bid = _best_px(ob.get("bids", []), "bid")
    ask = _best_px(ob.get("asks", []), "ask")
    spr = (ask - bid) if (ask is not None and bid is not None) else None
    return bid, ask, spr

async def get_market_meta(client: SignerClient, symbol: str) -> Optional[dict]:
    """Get market metadata (decimals, min sizes, etc.) for a symbol."""
    try:
        market_id = await resolve_market_id(client, symbol)
        if market_id is None:
            return None
            
        async with lighter.ApiClient(configuration=lighter.Configuration(host=client.url)) as api_client:
            order_api = lighter.OrderApi(api_client)
            ob = await order_api.order_book_details(market_id=market_id)
            details = ob.order_book_details[0] if ob.order_book_details else None
            if details:
                return {
                    "market_id": getattr(details, "market_id", market_id),
                    "symbol": getattr(details, "symbol", symbol),
                    "price_decimals": getattr(details, "price_decimals", 0),
                    "size_decimals": getattr(details, "size_decimals", 0),
                    "min_base_amount": getattr(details, "min_base_amount", "0"),
                    "min_quote_amount": getattr(details, "min_quote_amount", "0"),
                }
    except Exception as e:
        print(f"Error fetching market metadata for {symbol}: {e}")
    return None

# ------------------- Markets helpers -------------------
async def list_markets(client: SignerClient) -> List[str]:
    """Return a list of available market symbols using the SDK order_books endpoint."""
    try:
        from lighter import ApiClient, Configuration, OrderApi
        async with ApiClient(Configuration(host=client.url)) as cli:
            api = OrderApi(cli)
            
            ob = await api.order_books()
            def to_dict(x):
                if hasattr(x,'model_dump'): return x.model_dump()
                if hasattr(x,'dict'): return x.dict()
                return getattr(x,'__dict__', {})
            
            d = to_dict(ob)
            rows = d.get('order_books') or d.get('data') or []
            
            symbols = []
            for row in rows:
                rd = to_dict(row)
                symbol = rd.get("symbol") or rd.get("market") or rd.get("name")
                if symbol and symbol not in symbols:
                    symbols.append(symbol)
            
            return symbols
    except Exception as e:
        print(f"Error listing markets via SDK: {e}")
        return []

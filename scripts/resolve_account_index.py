#!/usr/bin/env python3
import asyncio, os, sys, json
from dotenv import load_dotenv
import lighter

NETWORK_TO_URL = {
    "mainnet": "https://mainnet.zklighter.elliot.ai",
    "testnet": "https://testnet.zklighter.elliot.ai",
}

USAGE = """
Usage:
  python scripts/resolve_account_index.py mainnet
  python scripts/resolve_account_index.py testnet

Reads L1_ADDRESS from configs/.env.<network> and prints ACCOUNT_INDEX.
Set WRITE_BACK_ACCOUNT_INDEX=true to persist it back to the env file.
"""

def envfile(network: str) -> str:
    return f"configs/.env.{network}"

def model_to_dict(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    return obj

def extract_index_from_any(payload):
    """
    Handles shapes:
      - {"account": {...}} or {...}
      - {"accounts": [ ... ]}
      - [ ... ]
    Prefers account_type == 0 if present.
    """
    d = model_to_dict(payload)

    # 1) Top-level account
    if isinstance(d, dict):
        if "account" in d and isinstance(d["account"], dict):
            acc = d["account"]
            return acc.get("account_index") or acc.get("index")

        # 2) Wrapped list of accounts
        if "accounts" in d and isinstance(d["accounts"], list):
            return pick_index_from_accounts_list(d["accounts"])

        # 3) Sometimes the fields are directly at top-level (rare)
        idx = d.get("account_index") or d.get("index")
        if idx is not None:
            return idx

    # 4) Raw list shape
    if isinstance(d, list):
        return pick_index_from_accounts_list(d)

    return None

def pick_index_from_accounts_list(accounts):
    """
    From a list of accounts, prefer account_type == 0 (primary/trading).
    Otherwise pick the first one that has index/account_index.
    """
    best = None
    # prefer primary/trading accounts
    for acc in accounts:
        a = model_to_dict(acc)
        if isinstance(a, dict) and a.get("account_type") == 0:
            return a.get("account_index") or a.get("index")
        if best is None and isinstance(a, dict):
            maybe = a.get("account_index") or a.get("index")
            if maybe is not None:
                best = maybe
    return best

def update_env_file(path: str, key: str, value: str) -> None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        lines = []
    out, seen = [], False
    for line in lines:
        if line.startswith(f"{key}="):
            out.append(f"{key}={value}\n")
            seen = True
        else:
            out.append(line)
    if not seen:
        out.append(f"{key}={value}\n")
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(out)

async def resolve_index(base_url: str, l1_addr: str):
    client = lighter.ApiClient(configuration=lighter.Configuration(host=base_url))
    try:
        acc_api = lighter.AccountApi(client)

        # 1) Prefer direct account lookup by L1
        data = await acc_api.account(by="l1_address", value=l1_addr)
        idx = extract_index_from_any(data)
        if idx is not None:
            return idx

        # 2) Fallback: list accounts by L1 and pick
        lst = await acc_api.accounts_by_l1_address(l1_address=l1_addr)
        idx = extract_index_from_any(lst)
        if idx is not None:
            return idx

        # 3) Debug dump if nothing found
        print("DEBUG payload (no index found):")
        try:
            print(json.dumps(model_to_dict(data), indent=2))
        except Exception:
            print(str(data))
        return None
    finally:
        await client.close()

async def main():
    if len(sys.argv) != 2 or sys.argv[1] not in NETWORK_TO_URL:
        print(USAGE); sys.exit(1)
    network = sys.argv[1]
    env_path = envfile(network)
    if not load_dotenv(env_path, override=True):
        print(f"Could not load env: {env_path}"); sys.exit(1)

    l1 = os.environ.get("L1_ADDRESS")
    if not l1:
        print(f"L1_ADDRESS not set in {env_path}"); sys.exit(1)

    idx = await resolve_index(NETWORK_TO_URL[network], l1)
    if idx is None:
        print("Could not resolve ACCOUNT_INDEX for that L1 address.")
        sys.exit(1)

    print(f"[{network}] L1_ADDRESS={l1}")
    print(f"[{network}] ACCOUNT_INDEX discovered: {idx}")

    if os.environ.get("WRITE_BACK_ACCOUNT_INDEX", "false").lower() in ("1","true","yes"):
        update_env_file(env_path, "ACCOUNT_INDEX", str(idx))
        print(f"Updated {env_path} with ACCOUNT_INDEX={idx}")

if __name__ == "__main__":
    asyncio.run(main())

# config environment
import os
from dotenv import load_dotenv
from pydantic import BaseModel

class Cfg(BaseModel):
    base_url: str
    account_index: int
    api_key_index: int
    eth_pk: str
    api_pk: str
    risk_max_risk_pct: float
    risk_daily_dd_stop: float
    risk_lev_cap: float
    max_concurrent: int

def load_cfg(env_file: str) -> Cfg:
    load_dotenv(env_file)
    return Cfg(
        base_url=os.environ["BASE_URL"],
        account_index=int(os.environ["ACCOUNT_INDEX"]),
        api_key_index=int(os.environ["API_KEY_INDEX"]),
        eth_pk=os.environ["ETH_PRIVATE_KEY"],
        api_pk=os.environ["API_KEY_PRIVATE_KEY"],
        risk_max_risk_pct=float(os.environ.get("RISK_MAX_RISK_PCT","0.5")),
        risk_daily_dd_stop=float(os.environ.get("RISK_DAILY_DD_STOP","2.0")),
        risk_lev_cap=float(os.environ.get("RISK_LEVERAGE_CAP","5")),
        max_concurrent=int(os.environ.get("MAX_CONCURRENT_POS","2")),
    )

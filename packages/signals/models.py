from pydantic import BaseModel
from typing import Optional, Literal


SignalType = Literal["OPEN", "CLOSE"]


class Signal(BaseModel):
    leader: str
    leader_account_index: int
    leader_l1: str
    market: str
    side: Literal["BUY", "SELL"]
    price: Optional[float] = None
    size: float
    type: SignalType
    client_ref: str
    ts: float


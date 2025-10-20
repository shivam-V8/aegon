from typing import Optional

from pydantic import BaseModel

from .enums import TIF_GTT

class OrderIntent(BaseModel):
    market: str
    side: str                 # "BUY" | "SELL"
    entry_px: Optional[float]
    stop_px: Optional[float]
    tp_px: Optional[float]
    base_amount: int
    tif: str = TIF_GTT

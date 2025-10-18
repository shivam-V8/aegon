from pydantic import BaseModel
from .enums import TIF_GTT

class OrderIntent(BaseModel):
    market: str
    side: str                 # "BUY" | "SELL"
    entry_px: float | None
    stop_px: float | None
    tp_px: float | None
    base_amount: int
    tif: str = TIF_GTT

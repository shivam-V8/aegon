# pydantic models (OrderCreate, etc.)from pydantic import BaseModel
from typing import Optional, Literal

Side = Literal["BUY","SELL"]

class OrderCreate(BaseModel):
    market: str
    side: Side
    order_type: str
    base_amount: str
    price: Optional[str] = None
    time_in_force: Optional[str] = None
    client_order_index: str

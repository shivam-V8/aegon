from packages.core.models.order import OrderIntent
def build_intent(market:str, side:str, entry:float|None,
                 stop:float|None, tp:float|None, base_amount:int):
    return OrderIntent(market=market, side=side, entry_px=entry, stop_px=stop, tp_px=tp, base_amount=base_amount)

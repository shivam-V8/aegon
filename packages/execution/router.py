from packages.core.usecases.place_bracket import build_create_orders
from .orders import place_bracket as exec_place_bracket

async def route_bracket(client, intent):
    creates = build_create_orders(intent)
    return await exec_place_bracket(client, creates)

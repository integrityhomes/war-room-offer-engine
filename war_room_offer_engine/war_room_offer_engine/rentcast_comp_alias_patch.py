from __future__ import annotations

try:
    import sold_comps as sold
except ImportError:
    try:
        from . import sold_comps as sold
    except ImportError:
        from war_room_offer_engine import sold_comps as sold


for alias in ["formattedAddress", "addressLine1"]:
    if alias not in sold.COMP_ALIASES["comp_address"]:
        sold.COMP_ALIASES["comp_address"].append(alias)

for alias in ["removedDate", "lastSeenDate"]:
    if alias not in sold.COMP_ALIASES["sold_date"]:
        sold.COMP_ALIASES["sold_date"].append(alias)

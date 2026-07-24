from __future__ import annotations

from copy import deepcopy


ILLINOIS_TARGET_ZIPS = [
    "62521", "62522", "62526", "62523", "62534", "62535", "62550",
    "62551", "62554", "62555", "62557", "62563", "62701", "62702",
    "62703", "62704", "62707", "62711", "61820", "61821", "61822",
    "61801", "61802", "61701", "61704", "61761", "61764",
]


# Only Illinois has verified production ZIP inputs today. Every other market is a
# disabled research candidate until its ZIP list, inventory, price/rent support,
# taxes, title/closing constraints, and buyer demand are validated. This prevents
# a broad multi-state rollout from silently creating expensive low-quality runs.
MARKET_REGISTRY = [
    {
        "market_id": "IL_CENTRAL_TARGET_ZIPS",
        "market_name": "Central Illinois — Current Target ZIPs",
        "state": "IL",
        "zip_codes": ILLINOIS_TARGET_ZIPS,
        "min_price": 20000,
        "max_price": 75000,
        "max_days_on_market": 14,
        "enabled": False,
        "rollout_wave": 1,
        "status": "mirror_ready",
        "buy_box_notes": "Mirror the existing Illinois task first; do not replace production until 14 scheduled runs pass.",
    },
    {
        "market_id": "MO_STL_VALUE_RING",
        "market_name": "St. Louis Value Ring",
        "state": "MO",
        "zip_codes": [],
        "min_price": 15000,
        "max_price": 90000,
        "max_days_on_market": 30,
        "enabled": False,
        "rollout_wave": 2,
        "status": "research",
        "buy_box_notes": "Seed cities: Dellwood, Moline Acres, Calverton Park, Flordell Hills, Riverview. Exclude Jennings unless separately approved.",
    },
    {
        "market_id": "IN_VALUE_MARKETS",
        "market_name": "Indiana Value Markets",
        "state": "IN",
        "zip_codes": [],
        "min_price": 15000,
        "max_price": 90000,
        "max_days_on_market": 30,
        "enabled": False,
        "rollout_wave": 2,
        "status": "research",
        "buy_box_notes": "Select ZIPs only after price, rent, tax, inventory, and buyer-demand scoring.",
    },
    {
        "market_id": "MI_TOLEDO_CORRIDOR",
        "market_name": "Southeast Michigan / Toledo Corridor",
        "state": "MI",
        "zip_codes": [],
        "min_price": 15000,
        "max_price": 100000,
        "max_days_on_market": 30,
        "enabled": False,
        "rollout_wave": 2,
        "status": "research",
        "buy_box_notes": "Research Monroe-area and nearby Michigan ZIPs; Ohio ZIPs belong in the Ohio market groups.",
    },
    {
        "market_id": "OH_CLEVELAND_VALUE",
        "market_name": "Cleveland Value Markets",
        "state": "OH",
        "zip_codes": [],
        "min_price": 15000,
        "max_price": 100000,
        "max_days_on_market": 30,
        "enabled": False,
        "rollout_wave": 3,
        "status": "research",
        "buy_box_notes": "Validate block-level demand, taxes, violations, title, and exit liquidity before enabling ZIPs.",
    },
    {
        "market_id": "OH_DAYTON_MANSFIELD",
        "market_name": "Dayton / Mansfield Value Markets",
        "state": "OH",
        "zip_codes": [],
        "min_price": 15000,
        "max_price": 100000,
        "max_days_on_market": 30,
        "enabled": False,
        "rollout_wave": 3,
        "status": "research",
        "buy_box_notes": "Separate ZIP groups after current listing and rent-support validation.",
    },
    {
        "market_id": "AL_VALUE_MARKETS",
        "market_name": "Alabama Value Markets",
        "state": "AL",
        "zip_codes": [],
        "min_price": 15000,
        "max_price": 100000,
        "max_days_on_market": 30,
        "enabled": False,
        "rollout_wave": 3,
        "status": "research",
        "buy_box_notes": "Select markets using inventory, rent-to-price, taxes, insurance, title, and buyer demand.",
    },
    {
        "market_id": "VA_SOUTHSIDE_VALUE",
        "market_name": "Southside Virginia Value Markets",
        "state": "VA",
        "zip_codes": [],
        "min_price": 20000,
        "max_price": 125000,
        "max_days_on_market": 45,
        "enabled": False,
        "rollout_wave": 3,
        "status": "research",
        "buy_box_notes": "Seed areas: Franklin, Courtland, Wakefield, Southampton County and nearby markets; verify well, septic, crawlspace and rural rent support.",
    },
    {
        "market_id": "TX_VALUE_MARKETS",
        "market_name": "Texas Value Markets — Research Queue",
        "state": "TX",
        "zip_codes": [],
        "min_price": 25000,
        "max_price": 125000,
        "max_days_on_market": 45,
        "enabled": False,
        "rollout_wave": 4,
        "status": "research",
        "buy_box_notes": "Do not enable statewide. Rank candidate ZIPs by listing supply, rent-to-price, taxes, insurance, title/closing friction and wholesale buyer liquidity.",
    },
]


def market_registry() -> list[dict]:
    return deepcopy(MARKET_REGISTRY)


def market_by_id(market_id: str) -> dict:
    return next((deepcopy(item) for item in MARKET_REGISTRY if item["market_id"] == market_id), {})


def enabled_markets() -> list[dict]:
    return [deepcopy(item) for item in MARKET_REGISTRY if item.get("enabled")]

from __future__ import annotations

import re
from typing import Any

try:
    import zillow_url_import as base
except ImportError:
    try:
        from . import zillow_url_import as base
    except ImportError:
        from war_room_offer_engine import zillow_url_import as base


def _money(value: Any) -> float:
    if value in [None, "", [], {}]:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = re.sub(r"[^0-9.\-]", "", str(value))
    try:
        return float(cleaned) if cleaned else 0.0
    except Exception:
        return 0.0


def safe_score_zillow_row(row: dict[str, Any], listing_url: str, address: str = "") -> int:
    """Score a Zillow row without crashing on values such as '$64,900'."""
    data = row.get("data", row) if isinstance(row, dict) else {}
    if not isinstance(data, dict):
        return -100

    score = 0
    target_zpid = base.extract_zpid(listing_url)
    row_zpid = str(data.get("zpid") or base.extract_zpid(str(data.get("listing_url") or "")))
    if target_zpid and row_zpid and target_zpid == row_zpid:
        score += 100

    target_url = base.canonical_url(listing_url)
    row_url = base.canonical_url(str(data.get("listing_url") or data.get("zillow_link") or ""))
    if target_url and row_url:
        if target_url == row_url:
            score += 80
        elif target_url in row_url or row_url in target_url:
            score += 50

    target_address = base.normalize_address(address)
    row_address = base.normalize_address(str(data.get("address") or ""))
    if target_address and row_address:
        if target_address == row_address:
            score += 70
        elif target_address in row_address or row_address in target_address:
            score += 35

    target_zip = base.extract_zip(address, listing_url)
    row_zip = str(data.get("zip") or "")
    if target_zip and row_zip and target_zip == row_zip:
        score += 10

    if row.get("ok", True):
        score += 5
    if _money(data.get("asking_price")) > 0:
        score += 5
    return score


base.score_zillow_row = safe_score_zillow_row

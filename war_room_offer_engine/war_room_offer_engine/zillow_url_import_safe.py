from __future__ import annotations

from typing import Any

try:
    import zillow_url_import as base
except ImportError:
    try:
        from . import zillow_url_import as base
    except ImportError:
        from war_room_offer_engine import zillow_url_import as base


is_zillow_url = base.is_zillow_url
extract_zpid = base.extract_zpid
extract_zip = base.extract_zip
build_zillow_actor_input = base.build_zillow_actor_input
extract_photo_urls = base.extract_photo_urls


def _first_nonblank(record: dict[str, Any], *keys: str) -> Any:
    lower = {str(key).lower(): key for key in record.keys()}
    for key in keys:
        actual = lower.get(key.lower())
        if actual is not None:
            value = record.get(actual)
            if value not in [None, "", 0, 0.0, [], {}]:
                return value
    return ""


def _enrich_from_raw(data: dict[str, Any], raw_record: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(data or {})
    aliases = {
        "listing_agent_name": ("agent_name", "agentName"),
        "listing_agent_phone": ("agent_phone", "agentPhone", "phone"),
        "listing_agent_email": ("agent_email", "agent_emai", "agentEmail"),
        "listing_brokerage": ("agent_brokerage", "brokerageName", "brokerName"),
        "rent": ("RC_Rent_Clean", "RC_Rent_Estimate", "rentZestimate", "rentEstimate"),
    }
    for target, keys in aliases.items():
        if enriched.get(target) in [None, "", 0, 0.0, [], {}]:
            value = _first_nonblank(raw_record, *keys)
            if value not in [None, "", 0, 0.0, [], {}]:
                enriched[target] = value

    photos = base.extract_photo_urls(raw_record or enriched)
    if photos:
        enriched["listing_photos"] = photos
        enriched["primary_photo"] = photos[0]
    return enriched


def _strict_match(rows: list[dict[str, Any]], listing_url: str, address: str = "") -> dict[str, Any] | None:
    if not rows:
        return None
    ranked = sorted(rows, key=lambda row: base.score_zillow_row(row, listing_url, address), reverse=True)
    best = ranked[0]
    score = base.score_zillow_row(best, listing_url, address)

    target_zpid = base.extract_zpid(listing_url)
    data = best.get("data", best) if isinstance(best, dict) else {}
    row_zpid = str(data.get("zpid") or base.extract_zpid(str(data.get("listing_url") or "")))
    target_address = base.normalize_address(address)
    row_address = base.normalize_address(str(data.get("address") or ""))

    exact_zpid = bool(target_zpid and row_zpid and target_zpid == row_zpid)
    exact_address = bool(target_address and row_address and target_address == row_address)
    strong_partial_address = bool(target_address and row_address and (target_address in row_address or row_address in target_address))

    if exact_zpid or exact_address:
        return best
    if strong_partial_address and score >= 35:
        return best
    return None


def pull_zillow_listing(listing_url: str, address: str = "", limit: int = 10) -> dict[str, Any]:
    url = str(listing_url or "").strip()
    if not base.is_zillow_url(url):
        return {
            "ok": False,
            "source": "Apify Zillow Live Pull",
            "error": "Paste a complete Zillow property URL beginning with https://.",
        }

    result = base._configured_result(url, address, max(int(limit or 10), 1))
    if not result.get("ok"):
        return result

    rows = result.get("rows", []) or []
    selected = _strict_match(rows, url, address)
    if selected is None:
        return {
            "ok": False,
            "source": result.get("source", "Apify Zillow Live Pull"),
            "error": "The ZIP scraper returned properties, but none safely matched the pasted Zillow URL or property address.",
            "row_count": len(rows),
        }

    data = dict(selected.get("data", {}) or {})
    data["listing_url"] = data.get("listing_url") or url
    data["zillow_link"] = data.get("zillow_link") or data["listing_url"]

    raw_items = result.get("raw_items", []) or []
    raw_record = base._raw_item_for_normalized_row(selected, raw_items) if raw_items else {}
    data = _enrich_from_raw(data, raw_record)

    required = ["address", "asking_price", "beds", "baths", "sqft"]
    missing = [field for field in required if data.get(field) in [None, "", 0, 0.0, [], {}]]
    warnings = list(selected.get("warnings", []) or [])
    if missing:
        warnings.append("Missing from Zillow pull: " + ", ".join(missing))

    return {
        "ok": True,
        "source": result.get("source", "Apify Zillow Live Pull"),
        "record": data,
        "selected_row": selected,
        "missing_fields": missing,
        "warnings": warnings,
        "row_count": len(rows),
        "configured_id": result.get("configured_id", ""),
        "actor_input": result.get("actor_input", {}),
    }

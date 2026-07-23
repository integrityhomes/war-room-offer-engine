from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit


MARKET_HEADERS = [
    "market_id", "market_name", "state", "zip_codes", "min_price", "max_price",
    "max_days_on_market", "enabled", "rollout_wave", "apify_task_id",
    "schedule_label", "buy_box_notes", "updated_at",
]

CURRENT_HEADERS = [
    "listing_key", "zpid", "address", "city", "state", "zip", "market_id",
    "asking_price", "original_price", "price_change", "price_change_percent",
    "beds", "baths", "sqft", "lot_size", "year_built", "property_type",
    "days_on_market", "listing_status", "listing_url", "primary_photo",
    "agent_name", "agent_email", "agent_phone", "agent_brokerage",
    "contact_source", "contact_verified_at", "first_seen", "last_seen",
    "last_run_id", "feed_status", "data_quality", "source",
]

HISTORY_HEADERS = [
    "event_id", "listing_key", "event_type", "field_name", "old_value",
    "new_value", "market_id", "run_id", "observed_at", "source",
]

QUEUE_HEADERS = [
    "listing_key", "assigned_to", "workflow_status", "last_contact_at",
    "next_follow_up", "agent_response", "team_notes", "dismiss_reason",
    "deal_id", "updated_by", "updated_at",
]

RUN_HEADERS = [
    "run_id", "market_id", "apify_task_id", "dataset_id", "started_at",
    "finished_at", "status", "items_received", "new_listings",
    "updated_listings", "price_changes", "duplicates", "quarantined",
    "cost_usd", "error", "processed_at",
]

QUARANTINE_HEADERS = [
    "quarantine_id", "run_id", "market_id", "reason", "raw_record_json",
    "observed_at",
]

SETUP_HEADERS = ["setting", "value", "instructions"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def number(value: Any) -> float:
    if value in [None, ""]:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = re.sub(r"[^0-9.\-]", "", str(value))
    try:
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0


def get_path(record: dict[str, Any], path: str) -> Any:
    current: Any = record
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def first_value(record: dict[str, Any], *paths: str) -> Any:
    for path in paths:
        value = get_path(record, path)
        if value not in [None, "", [], {}]:
            return value
    return ""


def normalize_address(value: Any) -> str:
    text = clean_text(value).lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    replacements = {
        " street ": " st ", " avenue ": " ave ", " road ": " rd ",
        " drive ": " dr ", " court ": " ct ", " lane ": " ln ",
        " place ": " pl ", " boulevard ": " blvd ", " highway ": " hwy ",
        " north ": " n ", " south ": " s ", " east ": " e ", " west ": " w ",
    }
    text = f" {text} "
    for old, new in replacements.items():
        text = text.replace(old, new)
    return re.sub(r"\s+", " ", text).strip()


def normalize_url(value: Any) -> str:
    text = clean_text(value)
    if not text:
        return ""
    if text.startswith("//"):
        text = "https:" + text
    elif text.startswith("s://"):
        text = "http" + text
    elif text.startswith("www."):
        text = "https://" + text
    try:
        parts = urlsplit(text)
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ""))
    except Exception:
        return text


def normalize_phone(value: Any) -> str:
    digits = re.sub(r"\D", "", clean_text(value))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits if len(digits) == 10 else ""


def listing_key(zpid: Any = "", address: Any = "", zip_code: Any = "", url: Any = "") -> str:
    zpid_digits = re.sub(r"\D", "", clean_text(zpid))
    if zpid_digits:
        return f"zpid:{zpid_digits}"
    normalized = normalize_address(address)
    zip_digits = re.sub(r"\D", "", clean_text(zip_code))[:5]
    if normalized and zip_digits:
        raw = f"{normalized}|{zip_digits}"
        return "address:" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]
    clean_url = normalize_url(url).lower()
    if clean_url:
        return "url:" + hashlib.sha1(clean_url.encode("utf-8")).hexdigest()[:20]
    return ""

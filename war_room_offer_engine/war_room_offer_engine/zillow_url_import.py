from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

import requests

try:
    from apify_connector import APIFY_API_BASE, fetch_dataset_items, normalize_address, normalize_zillow_records, run_actor_for_items
except ImportError:
    try:
        from .apify_connector import APIFY_API_BASE, fetch_dataset_items, normalize_address, normalize_zillow_records, run_actor_for_items
    except ImportError:
        from war_room_offer_engine.apify_connector import APIFY_API_BASE, fetch_dataset_items, normalize_address, normalize_zillow_records, run_actor_for_items


def get_secret(name: str, default: str = "") -> str:
    try:
        import streamlit as st

        value = st.secrets.get(name, default)
        return str(value).strip() if value is not None else default
    except Exception:
        return str(os.environ.get(name, default)).strip()


def is_zillow_url(value: str) -> bool:
    text = str(value or "").strip().lower()
    return text.startswith(("http://", "https://")) and ("zillow.com/" in text or "zillowstatic.com/" in text)


def clean_identifier(value: str, kind: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    patterns = {
        "task": [r"/actor-tasks/([^/?#]+)", r"/tasks/([^/?#]+)"],
        "actor": [r"/acts/([^/?#]+)", r"/actors/([^/?#]+)"],
        "dataset": [r"/datasets/([^/?#]+)"],
    }
    for pattern in patterns.get(kind, []):
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return text.rstrip("/").split("/")[-1].split("?")[0].split("#")[0].strip()


def extract_zpid(value: str) -> str:
    text = str(value or "")
    for pattern in [r"/(\d+)_zpid", r"[?&]zpid=(\d+)", r"\bzpid[\s:=\"']+(\d+)"]:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


def canonical_url(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parts = urlsplit(text)
        path = re.sub(r"/+", "/", parts.path).rstrip("/")
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))
    except Exception:
        return text.split("?", 1)[0].split("#", 1)[0].rstrip("/").lower()


def _template_actor_input(template_text: str, listing_url: str, address: str, limit: int) -> dict[str, Any]:
    if not template_text:
        return {}
    rendered = (
        str(template_text)
        .replace("{{LISTING_URL}}", listing_url)
        .replace("{{ZILLOW_URL}}", listing_url)
        .replace("{{ADDRESS}}", address)
        .replace("{{LIMIT}}", str(limit))
    )
    try:
        parsed = json.loads(rendered)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _replace_url_field(existing: Any, listing_url: str) -> Any:
    if isinstance(existing, list):
        if existing and isinstance(existing[0], dict):
            return [{"url": listing_url}]
        return [listing_url]
    if isinstance(existing, dict):
        return {"url": listing_url}
    return listing_url


def build_zillow_actor_input(
    listing_url: str,
    address: str = "",
    limit: int = 10,
    base_input: dict[str, Any] | None = None,
    template_text: str = "",
    input_mode: str = "",
) -> dict[str, Any]:
    templated = _template_actor_input(template_text, listing_url, address, limit)
    if templated:
        return templated

    payload = dict(base_input or {})
    known_url_fields = ["startUrls", "urls", "searchUrls", "listingUrls", "detailUrls", "url"]
    for key in known_url_fields:
        if key in payload:
            payload[key] = _replace_url_field(payload.get(key), listing_url)
            break
    else:
        normalized_mode = str(input_mode or "").strip().lower()
        if normalized_mode in {"url", "single_url"}:
            payload["url"] = listing_url
        elif normalized_mode in {"urls", "url_list"}:
            payload["urls"] = [listing_url]
        elif normalized_mode in {"searchurls", "search_urls"}:
            payload["searchUrls"] = [listing_url]
        elif normalized_mode in {"starturls_strings", "start_urls_strings"}:
            payload["startUrls"] = [listing_url]
        else:
            payload["startUrls"] = [{"url": listing_url}]

    for key in ["maxItems", "maxResults", "maxListings", "resultsLimit", "limit"]:
        if key in payload:
            payload[key] = max(int(limit or 10), 1)
    return payload


def fetch_task_input(task_id: str, token: str) -> dict[str, Any]:
    if not task_id or not token:
        return {}
    encoded_id = quote(task_id, safe="~")
    try:
        response = requests.get(
            f"{APIFY_API_BASE}/actor-tasks/{encoded_id}",
            params={"token": token},
            timeout=20,
        )
    except Exception:
        return {}
    if response.status_code < 200 or response.status_code >= 300:
        return {}
    try:
        body = response.json()
    except Exception:
        return {}
    data = body.get("data", body) if isinstance(body, dict) else {}
    task_input = data.get("input", {}) if isinstance(data, dict) else {}
    return task_input if isinstance(task_input, dict) else {}


def run_task_for_items(task_id: str, actor_input: dict[str, Any], token: str, limit: int = 10) -> dict[str, Any]:
    if not token:
        return {"ok": False, "source": "Apify Zillow Task", "error": "Missing Apify token"}
    if not task_id:
        return {"ok": False, "source": "Apify Zillow Task", "error": "Apify Zillow task id is required."}

    encoded_id = quote(task_id, safe="~")
    try:
        response = requests.post(
            f"{APIFY_API_BASE}/actor-tasks/{encoded_id}/run-sync-get-dataset-items",
            params={"token": token, "clean": "true", "format": "json", "limit": max(int(limit or 10), 1)},
            json=actor_input or {},
            timeout=180,
        )
    except Exception as exc:
        return {"ok": False, "source": "Apify Zillow Task", "error": f"Apify task request failed: {exc}"}

    if response.status_code in [401, 403]:
        return {"ok": False, "source": "Apify Zillow Task", "error": "Apify token cannot run the configured Zillow task."}
    if response.status_code < 200 or response.status_code >= 300:
        return {"ok": False, "source": "Apify Zillow Task", "error": f"Apify Zillow task failed HTTP {response.status_code}: {response.text[:300]}"}
    try:
        items = response.json()
    except Exception:
        return {"ok": False, "source": "Apify Zillow Task", "error": f"Apify Zillow task returned non-JSON data: {response.text[:250]}"}
    if not isinstance(items, list) or not items:
        return {"ok": False, "source": "Apify Zillow Task", "error": "Apify Zillow task returned no property rows."}

    normalized = normalize_zillow_records(items)
    normalized["source"] = "Apify Zillow Task"
    normalized["raw_items"] = items
    return normalized


def _candidate_photo_values(record: Any, depth: int = 0) -> list[str]:
    if depth > 5:
        return []
    urls: list[str] = []
    if isinstance(record, str):
        if record.startswith(("http://", "https://")) and any(token in record.lower() for token in [".jpg", ".jpeg", ".png", ".webp", "photos", "image"]):
            urls.append(record)
        return urls
    if isinstance(record, list):
        for item in record[:100]:
            urls.extend(_candidate_photo_values(item, depth + 1))
        return urls
    if not isinstance(record, dict):
        return urls

    photo_keys = {
        "photos",
        "photourls",
        "photoUrls",
        "images",
        "imageUrls",
        "responsivePhotos",
        "carouselPhotos",
        "media",
        "miniCardPhotos",
        "originalPhotos",
    }
    url_keys = {"url", "src", "href", "jpeg", "webp", "mixedSources"}
    for key, value in record.items():
        if str(key) in photo_keys or str(key) in url_keys or "photo" in str(key).lower() or "image" in str(key).lower():
            urls.extend(_candidate_photo_values(value, depth + 1))
    return urls


def extract_photo_urls(record: dict[str, Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for url in _candidate_photo_values(record):
        cleaned = str(url or "").strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result[:100]


def _raw_item_for_normalized_row(row: dict[str, Any], raw_items: list[dict[str, Any]]) -> dict[str, Any]:
    target_zpid = str(row.get("data", {}).get("zpid") or "")
    target_address = normalize_address(str(row.get("data", {}).get("address") or ""))
    for item in raw_items:
        text = json.dumps(item, default=str)
        if target_zpid and target_zpid in text:
            return item
        normalized = normalize_zillow_records([item]).get("rows", [])
        if normalized:
            candidate_address = normalize_address(str(normalized[0].get("data", {}).get("address") or ""))
            if target_address and candidate_address == target_address:
                return item
    return {}


def score_zillow_row(row: dict[str, Any], listing_url: str, address: str = "") -> int:
    data = row.get("data", row) if isinstance(row, dict) else {}
    if not isinstance(data, dict):
        return -100
    score = 0
    target_zpid = extract_zpid(listing_url)
    row_zpid = str(data.get("zpid") or extract_zpid(str(data.get("listing_url") or "")))
    if target_zpid and row_zpid and target_zpid == row_zpid:
        score += 100

    target_url = canonical_url(listing_url)
    row_url = canonical_url(str(data.get("listing_url") or data.get("zillow_link") or ""))
    if target_url and row_url:
        if target_url == row_url:
            score += 80
        elif target_url in row_url or row_url in target_url:
            score += 50

    target_address = normalize_address(address)
    row_address = normalize_address(str(data.get("address") or ""))
    if target_address and row_address:
        if target_address == row_address:
            score += 70
        elif target_address in row_address or row_address in target_address:
            score += 35

    if row.get("ok", True):
        score += 5
    if float(data.get("asking_price") or 0) > 0:
        score += 5
    return score


def select_matching_zillow_row(rows: list[dict[str, Any]], listing_url: str, address: str = "") -> dict[str, Any] | None:
    if not rows:
        return None
    ranked = sorted(rows, key=lambda row: score_zillow_row(row, listing_url, address), reverse=True)
    best = ranked[0]
    best_score = score_zillow_row(best, listing_url, address)
    if len(rows) == 1:
        return best
    return best if best_score > 5 else None


def _configured_result(listing_url: str, address: str, limit: int) -> dict[str, Any]:
    token = get_secret("APIFY_TOKEN", "") or get_secret("APIFY_API_TOKEN", "")
    if not token:
        return {"ok": False, "error": "APIFY_TOKEN is missing from Streamlit secrets.", "source": "Apify Zillow Live Pull"}

    task_id = clean_identifier(get_secret("APIFY_ZILLOW_TASK_ID", "") or get_secret("APIFY_TASK_ID", ""), "task")
    actor_id = clean_identifier(get_secret("APIFY_ZILLOW_ACTOR_ID", "") or get_secret("APIFY_ACTOR_ID", ""), "actor")
    dataset_id = clean_identifier(get_secret("APIFY_ZILLOW_DATASET_ID", "") or get_secret("APIFY_DATASET_ID", ""), "dataset")
    template_text = get_secret("APIFY_ZILLOW_INPUT_JSON", "")
    input_mode = get_secret("APIFY_ZILLOW_INPUT_MODE", "")

    if task_id:
        task_input = fetch_task_input(task_id, token)
        actor_input = build_zillow_actor_input(
            listing_url,
            address=address,
            limit=limit,
            base_input=task_input,
            template_text=template_text,
            input_mode=input_mode,
        )
        result = run_task_for_items(task_id, actor_input, token, limit=limit)
        result["configured_id"] = task_id
        result["actor_input"] = actor_input
        if result.get("ok"):
            return result

    if actor_id:
        actor_input = build_zillow_actor_input(
            listing_url,
            address=address,
            limit=limit,
            template_text=template_text,
            input_mode=input_mode,
        )
        result = run_actor_for_items(actor_id, actor_input, token, limit=limit)
        result["configured_id"] = actor_id
        result["actor_input"] = actor_input
        if result.get("ok"):
            return result

    if dataset_id:
        result = fetch_dataset_items(dataset_id, token, limit=max(limit, 25))
        result["configured_id"] = dataset_id
        if result.get("ok"):
            result["source"] = "Configured Apify Zillow Dataset"
            return result

    configured = [name for name, value in [("task", task_id), ("actor", actor_id), ("dataset", dataset_id)] if value]
    if configured:
        return result
    return {
        "ok": False,
        "source": "Apify Zillow Live Pull",
        "error": "No saved Zillow scraper is configured. Add APIFY_TASK_ID (preferred), APIFY_ZILLOW_ACTOR_ID, or APIFY_DATASET_ID to Streamlit secrets.",
    }


def pull_zillow_listing(listing_url: str, address: str = "", limit: int = 10) -> dict[str, Any]:
    url = str(listing_url or "").strip()
    if not is_zillow_url(url):
        return {"ok": False, "source": "Apify Zillow Live Pull", "error": "Paste a complete Zillow property URL beginning with https://."}

    result = _configured_result(url, address, max(int(limit or 10), 1))
    if not result.get("ok"):
        return result

    rows = result.get("rows", []) or []
    selected = select_matching_zillow_row(rows, url, address)
    if selected is None:
        return {
            "ok": False,
            "source": result.get("source", "Apify Zillow Live Pull"),
            "error": "The scraper returned rows, but none safely matched the pasted Zillow URL or property address.",
            "row_count": len(rows),
        }

    data = dict(selected.get("data", {}) or {})
    data["listing_url"] = data.get("listing_url") or url
    data["zillow_link"] = data.get("zillow_link") or data["listing_url"]

    raw_items = result.get("raw_items", []) or []
    raw_record = _raw_item_for_normalized_row(selected, raw_items) if raw_items else {}
    photos = extract_photo_urls(raw_record or data)
    if photos:
        data["listing_photos"] = photos
        data["primary_photo"] = photos[0]

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

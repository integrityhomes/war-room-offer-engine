from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent.parent
for path in [str(REPO_ROOT), str(APP_DIR.parent), str(APP_DIR)]:
    if path in sys.path:
        sys.path.remove(path)
    sys.path.insert(0, path)

schema = importlib.import_module("listing_radar_schema")
normalizer = importlib.import_module("listing_radar_normalizer")
markets = importlib.import_module("listing_radar_markets")
client = importlib.import_module("listing_radar_client")

for headers in [
    schema.MARKET_HEADERS,
    schema.CURRENT_HEADERS,
    schema.HISTORY_HEADERS,
    schema.QUEUE_HEADERS,
    schema.RUN_HEADERS,
    schema.QUARANTINE_HEADERS,
]:
    assert len(headers) == len(set(headers)), headers

raw = {
    "zpid": "12345678",
    "address": "101 Main Street",
    "city": "Decatur",
    "state": "il",
    "zipcode": "62521",
    "price": "$55,000",
    "bedrooms": 3,
    "bathrooms": 1,
    "livingArea": 1050,
    "daysOnZillow": 4,
    "agentName": "Test Agent",
    "agentPhone": "(217) 555-0101",
    "agentEmail": "agent@example.com",
    "brokerName": "Test Brokerage",
    "detailUrl": "https://www.zillow.com/homedetails/12345678_zpid/",
    "imgSrc": "s://photos.zillowstatic.com/test.jpg",
}
listing = normalizer.normalize_listing(
    raw,
    market_id="IL_CENTRAL_TARGET_ZIPS",
    run_id="run-1",
    observed_at="2026-07-23T12:00:00+00:00",
)
assert listing["listing_key"] == "zpid:12345678"
assert listing["state"] == "IL"
assert listing["asking_price"] == 55000
assert listing["agent_phone"] == "2175550101"
assert listing["primary_photo"].startswith("https://")
assert listing["data_quality"] == "Complete"

created, events = normalizer.merge_listing(None, listing)
assert created["feed_status"] == "NEW"
assert events and events[0]["event_type"] == "NEW_LISTING"

changed = dict(listing)
changed["asking_price"] = 50000
changed["last_seen"] = "2026-07-24T12:00:00+00:00"
changed["last_run_id"] = "run-2"
merged, events = normalizer.merge_listing(created, changed)
assert merged["asking_price"] == 50000
assert merged["original_price"] == 55000
assert merged["price_change"] == -5000
assert merged["feed_status"] == "PRICE_DROP"
assert any(event["event_type"] == "PRICE_DROP" for event in events)

same, events = normalizer.merge_listing(merged, dict(changed))
assert same["feed_status"] == "UNCHANGED"
assert not any(event["event_type"] == "PRICE_DROP" for event in events)

registry = markets.market_registry()
assert len(markets.ILLINOIS_TARGET_ZIPS) == 27
assert len(markets.ILLINOIS_TARGET_ZIPS) == len(set(markets.ILLINOIS_TARGET_ZIPS))
assert {item["state"] for item in registry} >= {"IL", "MO", "IN", "MI", "OH", "AL", "VA", "TX"}
assert all(item["enabled"] is False for item in registry)
assert markets.market_by_id("IL_CENTRAL_TARGET_ZIPS")["zip_codes"] == markets.ILLINOIS_TARGET_ZIPS

assert client.is_connected() in {True, False}

workspace_text = (APP_DIR / "single_section_workspace.py").read_text(encoding="utf-8")
assert '"📡 Listing Radar"' in workspace_text
assert "_render_listing_radar" in workspace_text

ui_text = (APP_DIR / "listing_radar_ui.py").read_text(encoding="utf-8")
assert "Analyze in Deal Engine" in ui_text
assert "decision_property_input" in ui_text
assert "lookup_rentcast" not in ui_text
assert "enrich_property_with_rentcast" not in ui_text
assert "RENTCAST_API_KEY" not in ui_text

setup_dir = REPO_ROOT / "setup" / "google_apps_script"
setup_text = (setup_dir / "ListingRadarV2_Setup.gs").read_text(encoding="utf-8")
ingest_text = (setup_dir / "ListingRadarV2_Ingest.gs").read_text(encoding="utf-8")
webapp_text = (setup_dir / "ListingRadarV2_WebApp.gs").read_text(encoding="utf-8")
combined = setup_text + ingest_text + webapp_text

for sheet_name in [
    "MARKETS",
    "LISTINGS_CURRENT",
    "LISTING_HISTORY",
    "TEAM_QUEUE",
    "RUN_LOG",
    "QUARANTINE",
]:
    assert sheet_name in combined

assert "LockService.getScriptLock" in ingest_text
assert "Authorization: 'Bearer ' + token" in ingest_text
assert "?token=" not in ingest_text
assert "PropertiesService.getScriptProperties" in combined
assert "function doPost(e)" in webapp_text
assert "update_queue" in webapp_text
assert not re.search(r"apify_api_[A-Za-z0-9_-]{10,}", combined)

print("Listing Radar Phase 1 foundation smoke test passed.")

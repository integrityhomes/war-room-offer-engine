from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pandas as pd

APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent.parent
for import_path in [str(REPO_ROOT), str(APP_DIR)]:
    if import_path in sys.path:
        sys.path.remove(import_path)
    sys.path.insert(0, import_path)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"OK: {message}")


module = importlib.import_module("zillow_url_import_safe")
zillow_url = "https://www.zillow.com/homedetails/1388-N-Walnut-Grove-Ave-Decatur-IL-62526/12345678_zpid/"

original_configured = module.base._configured_result
original_get_secret = module.base.get_secret
original_read_csv = module.pd.read_csv

try:
    module.base._configured_result = lambda *args, **kwargs: {
        "ok": False,
        "source": "Apify Zillow Live Pull",
        "error": "Missing APIFY_TOKEN",
    }
    module.base.get_secret = lambda name, default="": (
        "https://example.test/feed.csv" if name == "LEADS_SHEET_CSV_URL" else default
    )
    module.pd.read_csv = lambda url: pd.DataFrame(
        [
            {
                "zpid": "12345678",
                "address": "1388 N Walnut Grove Ave",
                "city": "Decatur",
                "state": "IL",
                "zip": "62526",
                "price": 64900,
                "beds": 3,
                "baths": 2,
                "sqft": 1450,
                "RC_Rent_Clean": 1250,
                "agent_name": "Test Agent",
                "agent_emai": "agent@example.com",
                "agent_phone": "2175551212",
                "agent_brokerage": "Test Realty",
                "url": zillow_url,
                "photo_all": "https://photos.zillowstatic.com/front.jpg\nhttps://photos.zillowstatic.com/kitchen.jpg",
            }
        ]
    )

    result = module.pull_zillow_listing(zillow_url)
    record = result["record"]
    check(result["ok"], "sheet fallback returns a successful property")
    check(result["source"] == "Leads/Master Feed Sheet", "sheet fallback source is identified")
    check(record["asking_price"] == 64900, "asking price maps from price")
    check(record["rent"] == 1250, "RC_Rent_Clean maps into rent")
    check(record["listing_agent_email"] == "agent@example.com", "agent_emai typo maps into agent email")
    check(len(record["listing_photos"]) == 2, "newline photo_all maps into a photo gallery")

    module.pd.read_csv = lambda url: pd.DataFrame([{"zpid": "99999999", "url": "https://www.zillow.com/other"}])
    failed_result = module.pull_zillow_listing(zillow_url)
    check(not failed_result.get("ok"), "import failure returns an unsuccessful result in offline tests")
    check(
        "analysis was stopped" in str(failed_result.get("error") or ""),
        "import failure stops analysis instead of using defaults",
    )
finally:
    module.base._configured_result = original_configured
    module.base.get_secret = original_get_secret
    module.pd.read_csv = original_read_csv

print("Zillow sheet fallback smoke test passed.")

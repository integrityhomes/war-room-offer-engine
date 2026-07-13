from __future__ import annotations

import importlib
import sys
from pathlib import Path


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


def import_first(*module_names: str):
    last_error: Exception | None = None
    for module_name in module_names:
        try:
            return importlib.import_module(module_name)
        except ImportError as exc:
            last_error = exc
    raise last_error or ImportError("No module names provided")


module = import_first(
    "zillow_url_import_safe",
    "war_room_offer_engine.zillow_url_import_safe",
    "war_room_offer_engine.war_room_offer_engine.zillow_url_import_safe",
)

url = "https://www.zillow.com/homedetails/1388-N-Walnut-Grove-Ave-Decatur-IL-62526/12345678_zpid/"
rows = [
    {
        "ok": True,
        "data": {
            "zpid": "99999999",
            "address": "999 Other St, Decatur IL 62526",
            "zip": "62526",
            "asking_price": "$52,500",
            "listing_url": "https://www.zillow.com/homedetails/999-Other-St/99999999_zpid/",
        },
    },
    {
        "ok": True,
        "data": {
            "zpid": "12345678",
            "address": "1388 N Walnut Grove Ave, Decatur IL 62526",
            "zip": "62526",
            "asking_price": "$64,900",
            "listing_url": url,
        },
    },
]

score = module._score_zillow_row(rows[1], url, "1388 N Walnut Grove Ave, Decatur IL 62526")
check(score > 100, "formatted Zillow price is scored without float conversion errors")
selected = module._strict_match(rows, url, "")
check(selected is rows[1], "exact ZPID is selected even when asking price is formatted text")
check(module._money("$64,900") == 64900, "formatted money converts safely")

print("Zillow failure guard smoke test passed.")

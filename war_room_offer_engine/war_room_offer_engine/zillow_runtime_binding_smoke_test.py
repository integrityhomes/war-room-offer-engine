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


def import_first(*module_names: str):
    last_error: Exception | None = None
    for module_name in module_names:
        try:
            return importlib.import_module(module_name)
        except ImportError as exc:
            last_error = exc
    raise last_error or ImportError("No module names provided")


safe_loader = import_first(
    "one_load_sources_safe",
    "war_room_offer_engine.one_load_sources_safe",
    "war_room_offer_engine.war_room_offer_engine.one_load_sources_safe",
)
score_patch = import_first(
    "zillow_score_patch",
    "war_room_offer_engine.zillow_score_patch",
    "war_room_offer_engine.war_room_offer_engine.zillow_score_patch",
)
zillow_safe = import_first(
    "zillow_url_import_safe",
    "war_room_offer_engine.zillow_url_import_safe",
    "war_room_offer_engine.war_room_offer_engine.zillow_url_import_safe",
)

assert zillow_safe.base.score_zillow_row is score_patch.safe_score_zillow_row

row = {
    "ok": True,
    "data": {
        "address": "1388 N Walnut Grove Ave, Decatur IL 62526",
        "zip": "62526",
        "asking_price": "$64,900",
        "listing_url": "https://www.zillow.com/homedetails/1388-N-Walnut-Grove-Ave-Decatur-IL-62526/12345678_zpid/",
        "zpid": "12345678",
    },
}
score = zillow_safe.base.score_zillow_row(
    row,
    row["data"]["listing_url"],
    row["data"]["address"],
)
assert score >= 100

selected = zillow_safe._strict_match(
    [row],
    row["data"]["listing_url"],
    row["data"]["address"],
)
assert selected is row

print("Zillow runtime binding smoke test passed.")

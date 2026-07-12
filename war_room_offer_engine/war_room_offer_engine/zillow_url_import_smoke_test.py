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
    "zillow_url_import",
    "war_room_offer_engine.zillow_url_import",
    "war_room_offer_engine.war_room_offer_engine.zillow_url_import",
)

zillow_url = "https://www.zillow.com/homedetails/1388-N-Walnut-Grove-Ave-Decatur-IL-62526/12345678_zpid/"

check(module.is_zillow_url(zillow_url), "Zillow property URL is recognized")
check(module.extract_zpid(zillow_url) == "12345678", "ZPID is extracted")

actor_input = module.build_zillow_actor_input(
    zillow_url,
    address="1388 N Walnut Grove Ave, Decatur IL 62526",
    limit=10,
)
check(actor_input == {"startUrls": [{"url": zillow_url}]}, "default actor input uses startUrls")

base_input = {"startUrls": [{"url": "https://www.zillow.com/old"}], "maxItems": 100}
merged_input = module.build_zillow_actor_input(zillow_url, limit=5, base_input=base_input)
check(merged_input["startUrls"] == [{"url": zillow_url}], "saved task URL is replaced")
check(merged_input["maxItems"] == 5, "saved task result limit is replaced")

template_input = module.build_zillow_actor_input(
    zillow_url,
    address="1388 N Walnut Grove Ave, Decatur IL 62526",
    limit=3,
    template_text='{"urls":["{{LISTING_URL}}"],"maxResults":{{LIMIT}}}',
)
check(template_input["urls"] == [zillow_url], "JSON template receives Zillow URL")
check(template_input["maxResults"] == 3, "JSON template receives result limit")

rows = [
    {
        "ok": True,
        "data": {
            "address": "999 Other St, Decatur IL 62526",
            "zpid": "99999999",
            "listing_url": "https://www.zillow.com/homedetails/999-Other-St/99999999_zpid/",
            "asking_price": 50000,
        },
    },
    {
        "ok": True,
        "data": {
            "address": "1388 N Walnut Grove Ave, Decatur IL 62526",
            "zpid": "12345678",
            "listing_url": zillow_url,
            "asking_price": 64900,
        },
    },
]
selected = module.select_matching_zillow_row(rows, zillow_url, "1388 N Walnut Grove Ave, Decatur IL 62526")
check(selected is rows[1], "exact Zillow property row is selected")

photos = module.extract_photo_urls(
    {
        "photos": [
            {"url": "https://photos.zillowstatic.com/fp/front.jpg"},
            {"mixedSources": {"jpeg": [{"url": "https://photos.zillowstatic.com/fp/kitchen.jpg"}]}},
        ]
    }
)
check("https://photos.zillowstatic.com/fp/front.jpg" in photos, "primary photo is extracted")
check("https://photos.zillowstatic.com/fp/kitchen.jpg" in photos, "nested photo is extracted")

bad_url = module.pull_zillow_listing("not-a-zillow-url")
check(not bad_url["ok"], "invalid URL fails safely")
check("complete Zillow property URL" in bad_url["error"], "invalid URL gives a useful message")

print("Zillow URL import smoke test passed.")

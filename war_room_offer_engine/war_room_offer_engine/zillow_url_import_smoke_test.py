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
address = "1388 N Walnut Grove Ave, Decatur IL 62526"

check(module.is_zillow_url(zillow_url), "Zillow property URL is recognized")
check(module.extract_zpid(zillow_url) == "12345678", "ZPID is extracted")
check(module.extract_zip_code(zillow_url, address) == "62526", "ZIP is extracted from Zillow URL/address")

actor_input = module.build_zillow_actor_input(
    zillow_url,
    address=address,
    limit=10,
    input_mode="zipcodes",
)
check(actor_input == {"zipCodes": ["62526"]}, "ZIP-search actor input uses the property ZIP")

saved_zip_input = {"zipCodes": ["61602", "61603"], "maxItems": 500}
merged_zip_input = module.build_zillow_actor_input(
    zillow_url,
    address=address,
    limit=25,
    base_input=saved_zip_input,
)
check(merged_zip_input["zipCodes"] == ["62526"], "saved task ZIP list is replaced with the subject ZIP")
check(merged_zip_input["maxItems"] == 25, "saved task result limit is reduced for one-property lookup")

url_actor_input = module.build_zillow_actor_input(
    zillow_url,
    address=address,
    limit=5,
    input_mode="starturls",
)
check(url_actor_input == {"startUrls": [{"url": zillow_url}]}, "URL actor mode remains supported")

template_input = module.build_zillow_actor_input(
    zillow_url,
    address=address,
    limit=3,
    template_text='{"zipCodes":["{{ZIP_CODE}}"],"maxResults":{{LIMIT}}}',
)
check(template_input["zipCodes"] == ["62526"], "JSON template receives the property ZIP")
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
            "address": address,
            "zpid": "12345678",
            "listing_url": zillow_url,
            "asking_price": 64900,
        },
    },
]
selected = module.select_matching_zillow_row(rows, zillow_url, address)
check(selected is rows[1], "exact Zillow property row is selected from ZIP results")

no_match = module.select_matching_zillow_row(rows, "https://www.zillow.com/homedetails/No-Match/55555555_zpid/", "1 Missing Ave, Decatur IL 62526")
check(no_match is None, "unmatched ZIP-search rows are rejected instead of importing the wrong house")

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

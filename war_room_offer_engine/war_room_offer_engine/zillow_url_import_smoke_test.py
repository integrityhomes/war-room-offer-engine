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

rows = [
    {
        "ok": True,
        "data": {
            "address": "999 Other St, Decatur IL 62526",
            "zpid": "99999999",
            "listing_url": "https://www.zillow.com/homedetails/999-Other-St/99999999_zpid/",
            "asking_price": "$50,000",
        },
    },
    {
        "ok": True,
        "data": {
            "address": address,
            "zpid": "12345678",
            "listing_url": zillow_url,
            "asking_price": {"value": "$64,900"},
        },
    },
]
selected = module._strict_match(rows, zillow_url, address)
check(selected is rows[1], "exact Zillow property row is selected from ZIP results")
check(module._score_zillow_row(rows[1], zillow_url, address) > 0, "nested formatted price does not crash scoring")
check(module._money("$64,900") == 64900, "formatted dollar price is cleaned")
check(module._money({"value": "$64,900"}) == 64900, "nested price object is cleaned")
check(module._money([{"amount": "64,900"}]) == 64900, "list-wrapped price is cleaned")

no_match = module._strict_match(
    rows,
    "https://www.zillow.com/homedetails/1-Missing-Ave-Decatur-IL-62526/55555555_zpid/",
    "",
)
check(no_match is None, "wrong ZIP-search rows are rejected")

raw_record = {
    "agent_name": "Stacy Spracklen",
    "agent_emai": "stacy@example.com",
    "agent_phone": "2175551212",
    "agent_brokerage": "Test Realty",
    "RC_Rent_Clean": "$1,100",
    "photo_all": "https://photos.zillowstatic.com/front.jpg\nhttps://photos.zillowstatic.com/kitchen.jpg",
}
enriched = module._enrich_from_raw({"asking_price": {"value": "$64,900"}}, raw_record)
check(enriched["asking_price"] == 64900, "existing nested asking price is normalized before analysis")
check(enriched["listing_agent_name"] == "Stacy Spracklen", "agent name auto-populates")
check(enriched["listing_agent_email"] == "stacy@example.com", "agent_emai typo auto-populates")
check(enriched["listing_agent_phone"] == "2175551212", "agent phone auto-populates")
check(enriched["listing_brokerage"] == "Test Realty", "brokerage auto-populates")
check(enriched["rent"] == 1100, "RC_Rent_Clean auto-populates")
check(len(enriched["listing_photos"]) == 2, "all newline-separated Zillow photos auto-populate")

bad_url = module.pull_zillow_listing("not-a-zillow-url")
check(not bad_url["ok"], "invalid URL fails safely outside Streamlit")
check("complete Zillow property URL" in bad_url["error"], "invalid URL gives a useful message")

print("Zillow URL import smoke test passed.")

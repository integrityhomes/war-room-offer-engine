from __future__ import annotations

import importlib
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent.parent.parent
for import_path in [str(REPO_ROOT), str(APP_DIR.parent), str(APP_DIR)]:
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
    "realtor_outreach_ui",
    "ui_sections.realtor_outreach_ui",
    "war_room_offer_engine.ui_sections.realtor_outreach_ui",
    "war_room_offer_engine.war_room_offer_engine.ui_sections.realtor_outreach_ui",
)

normalized = {
    "data": {
        "address": "307 W 5th St, Pana IL 62557",
        "asking_price": 42000,
        "listing_agent_name": "Stacy Spracklen",
        "listing_agent_phone": "2175551212",
        "listing_agent_email": "stacy@example.com",
        "listing_brokerage": "Test Realty",
        "listing_url": "https://www.zillow.com/homedetails/example",
        "listing_photos": [
            "https://photos.zillowstatic.com/front.jpg",
            "https://photos.zillowstatic.com/kitchen.jpg",
        ],
    },
    "first_offer": 28000,
    "internal_max": 32000,
    "final_decision": "Slow Flip",
}

package = module.build_visible_outreach_package(normalized)
contact = package["contact_package"]["contact"]
master = package["master_feed_fields"]

check(contact["name"] == "Stacy Spracklen", "visible panel receives agent name")
check(contact["email"] == "stacy@example.com", "visible panel receives agent email")
check(len(package["photos"]) == 2, "visible panel receives Zillow gallery")
check(master["Opening_Offer"] == 28000, "visible panel receives opening offer")
check(master["Max_Price"] == 32000, "visible panel receives internal max")
check("$28,000" in master["Opening_Message"], "visible panel receives copy-ready offer text")
check(master["Zillow_Link"].startswith("https://www.zillow.com/"), "visible panel receives Zillow link")

print("Realtor outreach UI smoke test passed.")

from __future__ import annotations

import importlib
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent.parent
for import_path in [str(REPO_ROOT), str(APP_DIR), str(APP_DIR / "ui_sections")]:
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


outreach = import_first(
    "realtor_outreach",
    "war_room_offer_engine.realtor_outreach",
    "war_room_offer_engine.war_room_offer_engine.realtor_outreach",
)
ui = import_first(
    "realtor_outreach_ui",
    "ui_sections.realtor_outreach_ui",
    "war_room_offer_engine.ui_sections.realtor_outreach_ui",
    "war_room_offer_engine.war_room_offer_engine.ui_sections.realtor_outreach_ui",
)

contact = outreach.extract_realtor_contact(
    {
        "agent_name": "Uptown Properties LLC",
        "agent_phone": "2125551212",
        "agent_brokerage": "Uptown Properties LLC",
    },
    {},
)
check(contact["name"] == "", "brokerage is not mislabeled as an individual agent")
check(contact["brokerage"] == "Uptown Properties LLC", "brokerage remains visible")
check(contact["phone"] == "(212) 555-1212", "full phone remains readable")

messages = outreach.build_first_touch_outreach(
    agent_name="Stacy Spracklen",
    address="1115 Matson Dr, Marion, VA 24354",
    offer_price=30000,
    asking_price=60000,
)
check("contingent on a walkthrough" in messages["text"].lower(), "first-touch text contains walkthrough contingency")
check("contingent on a walkthrough" in messages["email_body"].lower(), "offer email contains walkthrough contingency")
check("contingent on a walkthrough" in messages["follow_up_text"].lower(), "follow-up contains walkthrough contingency")

normalized = {
    "data": {
        "address": "1115 Matson Dr, Marion, VA 24354",
        "asking_price": 60000,
        "listing_agent_name": "Stacy Spracklen",
        "listing_agent_phone": "2765551212",
        "listing_agent_email": "stacy@example.com",
        "listing_brokerage": "Test Realty",
        "listing_url": "https://www.zillow.com/homedetails/example",
        "imgSrc": "https://photos.zillowstatic.com/front.jpg",
    },
    "first_offer": 30000,
    "internal_max": 44120,
    "final_decision": "Needs Human Review",
}
package = ui.build_visible_outreach_package(normalized)
check(package["photos"] == ["https://photos.zillowstatic.com/front.jpg"], "thumbnail photo fallback reaches the gallery")
check(package["master_feed_fields"]["Opening_Offer"] == 30000, "opening offer remains mapped")
check("contingent on a walkthrough" in package["master_feed_fields"]["Opening_Message"].lower(), "MASTER_FEED opening message contains walkthrough contingency")
check(ui._TEXT_WIDGET_SOURCES["one_load_property_address"] == "address", "visible property address autofill is configured")
check(ui._NUMBER_WIDGET_SOURCES["one_load_asking_price"] == "asking_price", "visible asking price autofill is configured")

print("Visible autofill and walkthrough smoke test passed.")

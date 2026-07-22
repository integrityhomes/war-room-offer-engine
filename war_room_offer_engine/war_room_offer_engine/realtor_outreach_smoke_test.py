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
    "realtor_outreach",
    "war_room_offer_engine.realtor_outreach",
    "war_room_offer_engine.war_room_offer_engine.realtor_outreach",
)

record = {
    "address": "307 W 5th St, Pana IL 62557",
    "agent_name": "Stacy Spracklen",
    "agent_emai": "stacy@example.com",
    "agent_phone": "2175551212",
    "agent_brokerage": "Test Realty",
    "photo_all": "https://photos.zillowstatic.com/front.jpg\nhttps://photos.zillowstatic.com/kitchen.jpg",
    "RC_Rent_Clean": 1100,
}

contact = module.extract_realtor_contact(record, {})
check(contact["name"] == "Stacy Spracklen", "agent name maps from raw feed")
check(contact["email"] == "stacy@example.com", "agent_emai typo is recognized")
check(contact["phone"] == "(217) 555-1212", "agent phone is normalized")
check(contact["brokerage"] == "Test Realty", "brokerage is recognized")

preferred_email = module.preferred_contact_method(contact, {"textable": None})
check(preferred_email == "Email", "email is preferred when textability is unknown")

preferred_text = module.preferred_contact_method(contact, {"textable": True})
check(preferred_text == "Text", "text is preferred when mobile is verified")

outreach = module.build_first_touch_outreach(
    agent_name=contact["name"],
    address=record["address"],
    offer_price=28000,
    asking_price=42000,
)
check("$28,000" in outreach["text"], "first-touch text includes the opening offer")
check("purchase as-is" in outreach["text"], "first-touch text includes as-is language")
email_body = str(outreach["email_body"] or "").lower()
check(
    "contingent" in email_body and "title" in email_body,
    "email keeps title-verification protection",
)
check("$28,000" in outreach["email_subject"], "email subject includes the offer")

master_fields = module.build_master_feed_fields(
    contact_package={
        "preferred_contact_method": "Text",
        "outreach": outreach,
        "phone_info": {"phone_type": "Mobile", "textable": True},
    },
    max_price=32000,
    opening_offer=28000,
    counter_offer_step=1000,
    next_counter_offer=29000,
    deal_type="Slow Flip",
    acquisition_priority="High",
    zillow_link="https://www.zillow.com/homedetails/example",
)
check(master_fields["Max_Price"] == 32000, "MASTER_FEED max price is produced")
check(master_fields["Opening_Offer"] == 28000, "MASTER_FEED opening offer is produced")
check(master_fields["Preferred_Contact_Method"] == "Text", "MASTER_FEED contact method is produced")
check(master_fields["Agent_Phone_Type"] == "Mobile", "phone type is produced")
check(master_fields["Agent_Textable"] == "Yes", "textability is produced")
check(master_fields["Opening_Message"] == outreach["text"], "MASTER_FEED opening message is produced")
check(master_fields["Follow_Up_Message"] == outreach["follow_up_text"], "MASTER_FEED follow-up is produced")

unknown = module.classify_phone("2175551212")
check(unknown["phone_type"] in {"Unknown", "Mobile", "Landline", "VoIP", "Toll Free", "Premium", "Shared Cost", "Pager"}, "phone classification fails safely")

print("Realtor outreach smoke test passed.")

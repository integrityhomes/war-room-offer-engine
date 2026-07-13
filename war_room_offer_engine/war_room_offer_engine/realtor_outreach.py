from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import quote

import requests


TWILIO_LOOKUP_URL = "https://lookups.twilio.com/v2/PhoneNumbers"


def get_secret(name: str, default: str = "") -> str:
    try:
        import streamlit as st

        value = st.secrets.get(name, default)
        return str(value).strip() if value is not None else default
    except Exception:
        return str(os.environ.get(name, default)).strip()


def first_nonblank(*values: Any) -> Any:
    for value in values:
        if value not in [None, "", 0, 0.0, [], {}]:
            return value
    return ""


def get_nested(record: dict[str, Any], path: str) -> Any:
    current: Any = record
    for part in str(path or "").split("."):
        if not isinstance(current, dict):
            return ""
        current = current.get(part)
        if current in [None, "", [], {}]:
            return ""
    return current


def pick(record: dict[str, Any], aliases: list[str]) -> Any:
    if not isinstance(record, dict):
        return ""
    lower = {str(key).lower(): key for key in record.keys()}
    for alias in aliases:
        value = get_nested(record, alias) if "." in alias else ""
        if value not in [None, "", [], {}]:
            return value
        key = lower.get(alias.lower())
        if key is not None and record.get(key) not in [None, "", [], {}]:
            return record.get(key)
    return ""


def normalize_phone(value: Any) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) == 10:
        return "+1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    if str(value or "").strip().startswith("+") and 8 <= len(digits) <= 15:
        return "+" + digits
    return str(value or "").strip()


def display_phone(value: Any) -> str:
    normalized = normalize_phone(value)
    digits = re.sub(r"\D", "", normalized)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return normalized


def normalize_email(value: Any) -> str:
    text = str(value or "").strip().lower()
    match = re.search(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}", text)
    return match.group(0) if match else ""


def extract_realtor_contact(record: dict[str, Any], normalized: dict[str, Any] | None = None) -> dict[str, str]:
    normalized = normalized or {}
    name = first_nonblank(
        normalized.get("listing_agent_name"),
        pick(record, ["agent_name", "agentName", "listedBy", "listingAgent.name", "attributionInfo.agentName"]),
    )
    phone = first_nonblank(
        normalized.get("listing_agent_phone"),
        pick(record, ["agent_phone", "agentPhone", "phone", "brokerPhone", "listingAgent.phone", "attributionInfo.agentPhoneNumber"]),
    )
    email = first_nonblank(
        normalized.get("listing_agent_email"),
        pick(record, ["agent_email", "agent_emai", "agentEmail", "listingAgent.email", "attributionInfo.agentEmail"]),
    )
    brokerage = first_nonblank(
        normalized.get("listing_brokerage"),
        pick(record, ["agent_brokerage", "brokerageName", "brokerName", "BrokerName", "attributionInfo.brokerName"]),
    )
    return {
        "name": str(name or "").strip(),
        "phone": display_phone(phone),
        "phone_e164": normalize_phone(phone),
        "email": normalize_email(email),
        "brokerage": str(brokerage or "").strip(),
    }


def _map_line_type(value: str) -> tuple[str, bool | None]:
    raw = str(value or "").strip().lower().replace("_", " ")
    if raw in {"mobile", "cellular", "wireless"}:
        return "Mobile", True
    if raw in {"landline", "fixed line", "fixed"}:
        return "Landline", False
    if raw in {"voip", "non fixed voip", "fixed voip"}:
        return "VoIP", None
    if raw in {"toll free", "premium", "shared cost", "pager"}:
        return raw.title(), False
    return "Unknown", None


def classify_phone(phone: str) -> dict[str, Any]:
    normalized = normalize_phone(phone)
    if not normalized:
        return {"phone_type": "Missing", "textable": False, "confidence": "Missing", "source": "None", "warning": "No realtor phone number was found."}

    account_sid = get_secret("TWILIO_ACCOUNT_SID", "")
    auth_token = get_secret("TWILIO_AUTH_TOKEN", "")
    if not account_sid or not auth_token:
        return {
            "phone_type": "Unknown",
            "textable": None,
            "confidence": "Not checked",
            "source": "No phone lookup configured",
            "warning": "Phone type is unknown. Do not assume the number can receive texts until verified.",
        }

    try:
        response = requests.get(
            f"{TWILIO_LOOKUP_URL}/{quote(normalized, safe='+')}",
            params={"Fields": "line_type_intelligence"},
            auth=(account_sid, auth_token),
            timeout=20,
        )
    except Exception as exc:
        return {"phone_type": "Unknown", "textable": None, "confidence": "Lookup failed", "source": "Twilio Lookup", "warning": f"Phone lookup failed: {exc}"}

    if response.status_code < 200 or response.status_code >= 300:
        return {"phone_type": "Unknown", "textable": None, "confidence": "Lookup failed", "source": "Twilio Lookup", "warning": f"Phone lookup returned HTTP {response.status_code}."}

    try:
        body = response.json()
    except Exception:
        return {"phone_type": "Unknown", "textable": None, "confidence": "Lookup failed", "source": "Twilio Lookup", "warning": "Phone lookup returned invalid data."}

    intelligence = body.get("line_type_intelligence") or {}
    error_code = intelligence.get("error_code")
    if error_code:
        return {"phone_type": "Unknown", "textable": None, "confidence": "Lookup incomplete", "source": "Twilio Lookup", "warning": f"Phone lookup error code: {error_code}"}

    phone_type, textable = _map_line_type(intelligence.get("type", ""))
    warning = ""
    if textable is False:
        warning = "This appears to be a landline or non-textable line. Call or email instead."
    elif textable is None:
        warning = "Text capability is not confirmed. Verify before sending SMS."
    return {"phone_type": phone_type, "textable": textable, "confidence": "Verified", "source": "Twilio Lookup", "warning": warning, "carrier": intelligence.get("carrier_name", "")}


def money(value: Any) -> str:
    try:
        amount = float(value or 0)
    except Exception:
        amount = 0
    return f"${amount:,.0f}" if amount > 0 else ""


def _first_name(name: str) -> str:
    text = str(name or "").strip()
    return text.split()[0] if text else "there"


def build_first_touch_outreach(
    *,
    agent_name: str,
    address: str,
    offer_price: Any = 0,
    asking_price: Any = 0,
    closing_days: int = 14,
    buyer_name: str = "our company",
) -> dict[str, str]:
    first_name = _first_name(agent_name)
    offer = money(offer_price)
    asking = money(asking_price)
    close_text = f"close in about {int(closing_days or 14)} days"

    if offer:
        text = (
            f"Hi {first_name}, this is Shawn. I’m reaching out about {address}. "
            f"We can offer {offer}, purchase as-is, and {close_text}. "
            "Is the seller open to reviewing that? Please text me back when you can."
        )
        subject = f"Offer for {address} — {offer}"
        email_body = (
            f"Hi {first_name},\n\n"
            f"I’m reaching out regarding {address}. Based on the information currently available, "
            f"we can offer {offer}, purchase the property as-is, and {close_text}. "
            "The offer would be subject to confirming title, access, and the property information provided.\n\n"
            "Please let me know whether the seller is open to reviewing this or if there is a price range that would receive serious consideration.\n\n"
            "Thank you,\nShawn"
        )
    else:
        price_reference = f" The current asking price appears to be {asking}." if asking else ""
        text = (
            f"Hi {first_name}, this is Shawn. I’m looking at {address}.{price_reference} "
            "Is it still available, and does the seller have any flexibility for an as-is purchase with a clean closing?"
        )
        subject = f"Question about {address}"
        email_body = (
            f"Hi {first_name},\n\n"
            f"I’m reviewing {address}.{price_reference} Is the property still available, and does the seller have any flexibility "
            "for an as-is purchase with a straightforward closing? If so, please share any known repairs, occupancy details, and the seller’s timing.\n\n"
            "Thank you,\nShawn"
        )

    follow_up = (
        f"Hi {first_name}, following up on {address}. Were you able to confirm whether the seller would consider "
        + (f"the {offer} as-is offer" if offer else "an as-is offer below asking")
        + "?"
    )
    return {"text": text, "email_subject": subject, "email_body": email_body, "follow_up_text": follow_up}


def preferred_contact_method(contact: dict[str, Any], phone_info: dict[str, Any]) -> str:
    if contact.get("phone") and phone_info.get("textable") is True:
        return "Text"
    if contact.get("email"):
        return "Email"
    if contact.get("phone"):
        return "Call"
    return "Needs agent contact lookup"


def build_realtor_contact_package(
    *,
    record: dict[str, Any],
    normalized: dict[str, Any],
    offer_price: Any = 0,
    asking_price: Any = 0,
) -> dict[str, Any]:
    contact = extract_realtor_contact(record, normalized)
    phone_info = classify_phone(contact.get("phone_e164") or contact.get("phone", ""))
    outreach = build_first_touch_outreach(
        agent_name=contact.get("name", ""),
        address=str(normalized.get("address") or record.get("address") or "the property"),
        offer_price=offer_price,
        asking_price=asking_price or normalized.get("asking_price", 0),
    )
    return {
        "contact": contact,
        "phone_info": phone_info,
        "preferred_contact_method": preferred_contact_method(contact, phone_info),
        "outreach": outreach,
    }


def build_master_feed_fields(
    *,
    contact_package: dict[str, Any],
    max_price: Any = 0,
    opening_offer: Any = 0,
    next_counter_offer: Any = 0,
    counter_offer_step: Any = 0,
    deal_type: str = "",
    acquisition_priority: str = "Review",
    zillow_link: str = "",
) -> dict[str, Any]:
    outreach = contact_package.get("outreach", {}) or {}
    phone_info = contact_package.get("phone_info", {}) or {}
    behavior = "Unknown — verify responsiveness, seller flexibility, repairs, timing, and preferred contact method."
    strategy = "Send the first-touch message, confirm availability and seller flexibility, then negotiate without exceeding the Deal Engine internal max."
    return {
        "Max_Price": max_price or "",
        "Offer_Price": opening_offer or "",
        "Offer_Base": opening_offer or "",
        "Opening_Offer": opening_offer or "",
        "Counter_Offer_Step": counter_offer_step or "",
        "Next_Counter_Offer": next_counter_offer or "",
        "Agent_Behavior": behavior,
        "Negotiation_Strategy": strategy,
        "Preferred_Contact_Method": contact_package.get("preferred_contact_method", "Needs agent contact lookup"),
        "Opening_Message": outreach.get("text", ""),
        "Follow_Up_Message": outreach.get("follow_up_text", ""),
        "Deal_Type": deal_type,
        "Deal_Type_Auto": deal_type,
        "Internal_Status": "New",
        "Acq_Status": "New",
        "Acq_Priority": acquisition_priority,
        "Zillow_Link": zillow_link,
        "Agent_Phone_Type": phone_info.get("phone_type", "Unknown"),
        "Agent_Textable": "Yes" if phone_info.get("textable") is True else "No" if phone_info.get("textable") is False else "Unknown",
    }

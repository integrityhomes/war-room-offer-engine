from __future__ import annotations

import re
from typing import Any

try:
    from data_sources import (
        money_to_float,
        parse_listing_text,
        parse_universal_listing_text,
        universal_listing_from_record,
    )
except ImportError:
    try:
        from .data_sources import (
            money_to_float,
            parse_listing_text,
            parse_universal_listing_text,
            universal_listing_from_record,
        )
    except ImportError:
        from war_room_offer_engine.data_sources import (
            money_to_float,
            parse_listing_text,
            parse_universal_listing_text,
            universal_listing_from_record,
        )


def parse_seller_notes(text: str) -> dict[str, Any]:
    compact = re.sub(r"\s+", " ", str(text or "")).strip()
    parsed_listing = parse_listing_text(compact)

    def find_text(patterns: list[str]) -> str:
        for pattern in patterns:
            match = re.search(pattern, compact, re.IGNORECASE)
            if match:
                value = match.group(1) if match.lastindex else match.group(0)
                return value.strip(" .;,-")
        return ""

    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", compact)
    phone_match = re.search(r"(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}", compact)
    repairs = find_text(
        [
            r"(?:repairs?|condition|needs)[:\s]+(.+?)(?:\.| timeline| asking| price| occupancy| access|$)",
            r"(?:roof|hvac|plumbing|electrical|kitchen|bath|flooring|paint|foundation|termite|water damage|mold)[^.]*",
        ]
    )
    motivation = find_text([r"(?:motivation|why selling|reason)[:\s]+(.+?)(?:\.| timeline| asking| price|$)"])
    timeline = find_text([r"(?:timeline|needs to close|close by|when)[:\s]+(.+?)(?:\.| asking| price|$)"])
    occupancy = find_text([r"(?:occupancy|occupied|vacant)[:\s]+(vacant|tenant occupied|owner occupied|occupied|unknown)"])
    access = find_text([r"(?:access|showing)[:\s]+(.+?)(?:\.|$)"])
    seller_name = find_text([r"(?:seller|owner|name)[:\s]+([A-Za-z .'-]{2,80})"])
    desired_price = money_to_float(find_text([r"(?:seller wants|desired price|asking|ask|price)[:\s$]+([\d,]+)"]))
    mortgage_balance = money_to_float(find_text([r"(?:mortgage balance|payoff|loan balance)[:\s$]+([\d,]+)"]))
    return {
        "seller_name": seller_name,
        "seller_phone": phone_match.group(0) if phone_match else "",
        "seller_email": email_match.group(0) if email_match else "",
        "seller_motivation": motivation,
        "seller_timeline": timeline,
        "seller_desired_price": desired_price,
        "seller_condition_notes": compact,
        "seller_repair_notes": repairs,
        "seller_mortgage_balance": mortgage_balance,
        "occupancy": occupancy.title() if occupancy else "",
        "access_notes": access,
        "parsed_listing": parsed_listing,
    }


def one_load_review_before_offer_checklist() -> list[str]:
    return [
        "Verify bed/bath count",
        "Verify ownership/title",
        "Verify seller authority",
        "Verify sold comps",
        "Verify rent comps",
        "Verify repair scope",
        "Verify occupancy",
        "Verify buyer demand",
        "Verify contract status before sharing full address",
    ]


def one_load_status_checklist(summary: dict[str, Any]) -> list[dict[str, str]]:
    missing = set(summary.get("missing_critical_fields", []))
    arv_confidence = str(summary.get("arv_confidence", "Not enough data"))
    rent_confidence = str(summary.get("rent_confidence", "Weak"))
    buyer_demand = str(summary.get("buyer_demand_confidence", "Unknown"))
    deal_protection = str(summary.get("deal_protection_status", "Yes"))
    return [
        {"status": "ok" if "address" not in missing else "warning", "label": "Property facts imported"},
        {"status": "ok" if "asking price" not in missing else "warning", "label": "Asking price imported"},
        {"status": "warning" if rent_confidence in ["Weak", "Unknown", "Not enough data"] else "ok", "label": "Rent comps weak"},
        {"status": "warning" if arv_confidence in ["Weak", "AVM only", "Not enough data"] else "ok", "label": "Fewer than 3 good comps"},
        {"status": "warning" if buyer_demand in ["Unknown", "Weak"] else "ok", "label": "Buyer demand not verified"},
        {"status": "ok" if deal_protection == "Yes" else "warning", "label": "Deal protection active"},
        {"status": "ok" if summary.get("final_simple_answer") else "warning", "label": "Final decision generated"},
    ]


def normalize_one_load_lead(payload: dict[str, Any]) -> dict[str, Any]:
    payload = payload or {}
    lead_type = str(payload.get("lead_type", "") or "Manual quick entry")
    lead_source = str(payload.get("lead_source", "") or "Other")
    input_method = str(payload.get("input_method", "") or "Manual quick entry")
    listing_url = str(payload.get("listing_url", "") or "")
    address = str(payload.get("property_address", "") or "")
    listing_text = str(payload.get("listing_text", "") or "")
    seller_notes = str(payload.get("seller_notes", "") or "")
    record = payload.get("record", {}) if isinstance(payload.get("record", {}), dict) else {}
    combined_text = "\n".join(part for part in [address, listing_url, listing_text, seller_notes] if part)
    seller = parse_seller_notes(seller_notes or listing_text)

    if record:
        universal = universal_listing_from_record(record, source=lead_source, listing_url=listing_url)
    else:
        universal = parse_universal_listing_text(lead_source, listing_url, combined_text)

    data = dict(universal.get("data", {}) or {})
    parsed_from_notes = seller.get("parsed_listing", {})
    for key, parsed_key in [
        ("address", "address"),
        ("city", "city"),
        ("state", "state"),
        ("zip", "zip"),
        ("asking_price", "asking_price"),
        ("beds", "beds"),
        ("baths", "baths"),
        ("sqft", "sqft"),
        ("days_on_market", "days_on_market"),
    ]:
        if data.get(key) in ["", 0, 0.0, None] and parsed_from_notes.get(parsed_key) not in ["", 0, 0.0, None]:
            data[key] = parsed_from_notes.get(parsed_key)

    manual_fields = {
        "asking_price": payload.get("asking_price"),
        "seller_desired_price": payload.get("seller_desired_price"),
        "occupancy": payload.get("occupancy"),
        "listing_agent_name": payload.get("contact_name"),
        "listing_agent_phone": payload.get("contact_phone"),
        "listing_agent_email": payload.get("contact_email"),
    }
    for key, value in manual_fields.items():
        if value not in [None, "", 0, 0.0, [], {}]:
            if key == "seller_desired_price" and data.get("asking_price") in ["", 0, 0.0, None]:
                data["asking_price"] = value
            elif key != "seller_desired_price":
                data[key] = value

    if address and not data.get("address"):
        data["address"] = address
    if seller.get("seller_desired_price") and data.get("asking_price") in ["", 0, 0.0, None]:
        data["asking_price"] = seller["seller_desired_price"]
    if seller.get("occupancy") and not data.get("occupancy"):
        data["occupancy"] = seller["occupancy"]

    critical_fields = {
        "address": data.get("address"),
        "asking price": data.get("asking_price"),
        "beds": data.get("beds"),
        "baths": data.get("baths"),
        "sqft": data.get("sqft"),
        "ARV": data.get("sheet_arv"),
        "rent": data.get("rent"),
        "repairs": payload.get("manual_repair_estimate") or seller.get("seller_repair_notes"),
    }
    missing = [key for key, value in critical_fields.items() if value in ["", 0, 0.0, None, [], {}]]
    data_sources_used = [lead_source]
    if listing_url:
        data_sources_used.append("Listing URL")
    if record:
        data_sources_used.append("Imported record")
    if listing_text:
        data_sources_used.append("Pasted listing text")
    if seller_notes:
        data_sources_used.append("Seller notes")

    arv_confidence = "Weak" if data.get("sheet_arv") in ["", 0, 0.0, None] else "AVM only"
    rent_confidence = "Weak" if data.get("rent") in ["", 0, 0.0, None] else "Medium"
    repair_source = "Seller notes" if seller.get("seller_repair_notes") else "Manual" if payload.get("manual_repair_estimate") else "Missing"
    success = bool(data.get("address") or data.get("asking_price") or seller_notes or listing_text or record)
    summary = {
        "one_load_run_success": "Yes" if success else "No",
        "lead_type": lead_type,
        "lead_source": lead_source,
        "input_method": input_method,
        "input_value": listing_url or address or input_method,
        "data": data,
        "seller": seller,
        "missing_critical_fields": missing,
        "data_sources_used": sorted(set(data_sources_used)),
        "arv_source": "Imported AVM/listing value" if data.get("sheet_arv") else "Missing",
        "arv_confidence": arv_confidence,
        "rent_confidence": rent_confidence,
        "repair_source": repair_source,
        "buyer_demand_confidence": payload.get("buyer_demand_confidence", "Unknown"),
        "deal_protection_status": payload.get("deal_protection_mode", "Yes"),
        "field_sources": universal.get("field_sources", {}),
        "warnings": universal.get("warnings", []) + universal.get("conflict_flags", []),
        "errors": universal.get("errors", []),
        "manual_review_needed": "Yes" if missing or lead_type != "On-market listing" else universal.get("manual_review_needed", "Yes"),
    }
    summary["status_checklist"] = one_load_status_checklist(summary)
    summary["review_before_offer_checklist"] = one_load_review_before_offer_checklist()
    return summary

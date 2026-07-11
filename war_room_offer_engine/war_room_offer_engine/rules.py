from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Dict, Any


@dataclass
class Assumptions:
    min_assignment_fee: float = 10000
    exception_assignment_fee: float = 5000
    slow_flip_rent_multiple: float = 45
    close_title_buffer: float = 1500
    target_offer_discount: float = 0.85
    wholesale_buyer_percent_arv: float = 0.70
    wholesale_buyer_percent_source: str = "Market Default"
    wholesale_buyer_percent_range: str = ""
    wholesale_buyer_percent_reason: str = ""
    market_liquidity_tier: str = ""
    market_wholesale_buyer_percent: float = 0.70
    slow_flip_max_offer_cap: float = 32000
    slow_flip_first_offer_gap: float = 4000
    slow_flip_lead_search_max: float = 0
    slow_flip_lead_search_source: str = "Market Default"
    above_slow_flip_lead_search_range: bool = False
    inside_slow_flip_lead_search_range: bool = False
    slow_flip_max_buy_price: float = 0
    slow_flip_max_source: str = "Market Default"
    above_slow_flip_max_buy_price: bool = False


def build_default_assumptions_for_test() -> Assumptions:
    return Assumptions(
        min_assignment_fee=10000,
        exception_assignment_fee=5000,
        slow_flip_rent_multiple=45,
        close_title_buffer=1500,
        target_offer_discount=0.85,
        wholesale_buyer_percent_arv=0.70,
        wholesale_buyer_percent_source="Market Default",
        wholesale_buyer_percent_range="",
        wholesale_buyer_percent_reason="Smoke test default",
        market_liquidity_tier="Normal investor market",
        market_wholesale_buyer_percent=0.70,
        slow_flip_max_offer_cap=32000,
        slow_flip_first_offer_gap=4000,
        slow_flip_lead_search_max=85000,
        slow_flip_lead_search_source="Market Default",
        above_slow_flip_lead_search_range=False,
        inside_slow_flip_lead_search_range=True,
        slow_flip_max_buy_price=50000,
        slow_flip_max_source="Market Default",
        above_slow_flip_max_buy_price=False,
    )


@dataclass
class DealInput:
    address: str
    market: str
    lead_type: str
    exit_mode: str
    asking_price: float
    rent: float
    beds: float
    baths: float
    sqft: float
    taxes: float
    status: str
    occupancy: str
    livable: str
    days_on_market: int
    notes: str
    arv: float = 0
    repairs: float = 0


def money(value: float) -> str:
    try:
        return "${:,.0f}".format(float(value))
    except Exception:
        return "$0"


PRE_CONTRACT_STATUSES = {"Not under contract", "Offer sent", "Verbal agreement"}
FULL_PACKAGE_STATUSES = {"Under contract", "Closed / owned"}
DEAL_PROTECTION_WARNING = (
    "Deal is not under contract. Use teaser only. Do not share exact address, "
    "seller/source details, parcel ID, or listing link."
)
SENSITIVE_BUYER_FIELDS = [
    "exact address",
    "seller/source details",
    "owner name",
    "listing agent phone/email",
    "listing/source links",
    "parcel ID/APN",
    "county owner record link",
    "photos with house number or street sign",
]


def contract_allows_full_buyer_package(contract_status: str) -> bool:
    return str(contract_status or "") in FULL_PACKAGE_STATUSES


def default_address_sharing_level(contract_status: str) -> str:
    return "Full address allowed" if contract_allows_full_buyer_package(contract_status) else "Hide exact address"


def default_listing_source_sharing_level(contract_status: str) -> str:
    return "Full links allowed" if contract_allows_full_buyer_package(contract_status) else "Hide listing/source links"


def _sanitize_protected_condition_text(text: str, mold_verified: bool = False) -> str:
    clean = str(text or "")
    if mold_verified:
        return clean
    replacements = {
        "black mold": "suspected biological growth",
        "mold remediation": "moisture/biological growth verification allowance",
        "visible mold": "visible discoloration",
        "mold": "moisture staining/discoloration",
    }
    for old, new in replacements.items():
        clean = re.sub(old, new, clean, flags=re.IGNORECASE)
    return clean


def _area_label(context: dict, hide_exact: bool) -> str:
    city = str(context.get("city") or "").strip()
    market = str(context.get("market") or "").strip()
    county = str(context.get("county") or "").strip()
    state = str(context.get("state") or "").strip()
    address = str(context.get("address") or "").strip()
    if not hide_exact and address:
        return address
    if city and state:
        return f"{city} {state} area"
    if city:
        return f"{city} area"
    if county:
        return f"{county} county area"
    if market:
        return f"{market} area"
    return "this area"


def _bed_bath_label(context: dict) -> str:
    beds = context.get("beds", "")
    baths = context.get("baths", "")
    try:
        beds_text = f"{float(beds):g} bed" if float(beds or 0) > 0 else ""
    except Exception:
        beds_text = ""
    try:
        baths_text = f"{float(baths):g} bath" if float(baths or 0) > 0 else ""
    except Exception:
        baths_text = ""
    if beds_text and baths_text:
        return f"{beds_text} / {baths_text}"
    return beds_text or baths_text or "property"


def build_deal_protection_payload(context: dict) -> dict:
    contract_status = str(context.get("contract_status") or "Not under contract")
    protect_mode = str(context.get("deal_protection_mode") or "Yes")
    address_level = str(context.get("address_sharing_level") or default_address_sharing_level(contract_status))
    listing_level = str(context.get("listing_source_sharing_level") or default_listing_source_sharing_level(contract_status))
    buyer_message_type = str(context.get("buyer_message_type") or "Pre-contract demand check")
    locked = contract_allows_full_buyer_package(contract_status)
    protect_on = protect_mode == "Yes"
    exact_address_shared = locked and address_level == "Full address allowed"
    listing_shared = locked and listing_level == "Full links allowed"
    full_blast_allowed = locked and (not protect_on or locked)
    buyer_message_allowed = "Full Blast Allowed" if full_blast_allowed else "Teaser Only"

    protected_fields_hidden = []
    if not exact_address_shared:
        protected_fields_hidden.append("exact address")
    if protect_on or not locked:
        protected_fields_hidden.extend(
            [
                "seller/source details",
                "owner name",
                "listing agent phone/email",
                "parcel ID/APN",
                "county owner record link",
                "photos with house number or street sign",
            ]
        )
    if not listing_shared:
        protected_fields_hidden.append("listing/source links")
    protected_fields_hidden = list(dict.fromkeys(protected_fields_hidden))

    mold_verified = bool(context.get("mold_verified", False))
    notes = _sanitize_protected_condition_text(context.get("notes", ""), mold_verified)
    repair_notes = _sanitize_protected_condition_text(context.get("repair_notes", ""), mold_verified)
    area = _area_label(context, hide_exact=not exact_address_shared)
    bed_bath = _bed_bath_label(context)
    arv = float(context.get("arv", 0) or 0)
    repairs = float(context.get("repairs", 0) or 0)
    price = float(context.get("asking_price", 0) or 0)
    listing_url = str(context.get("listing_url") or "").strip()
    access_notes = _sanitize_protected_condition_text(context.get("access_notes", ""), mold_verified)
    deadline = str(context.get("buyer_deadline") or "").strip()

    condition_bits = []
    if arv > 0:
        condition_bits.append(f"ARV around {money(arv)}")
    else:
        condition_bits.append("lower ARV range")
    if repairs > 0:
        condition_bits.append(f"needs about {money(repairs)} in work")
    else:
        condition_bits.append("needs work")
    combined_notes = " ".join(part for part in [notes, repair_notes] if str(part or "").strip())
    if combined_notes:
        condition_bits.append(combined_notes[:180])

    pre_contract_teaser = (
        f"Checking buyer demand for a possible deal in the {area}. "
        f"{bed_bath}, {', '.join(condition_bits)}. "
        "Who is buying this area, and what price range would you need?"
    )

    blast_lines = [
        "Buyer deal package:",
        f"Address: {context.get('address', '') if exact_address_shared else area}",
        f"Property: {bed_bath}",
        f"Price: {money(price)}" if price > 0 else "Price: TBD",
        f"ARV: {money(arv)}" if arv > 0 else "ARV: verify",
        f"Repairs: {money(repairs)}" if repairs > 0 else "Repairs: verify",
    ]
    if listing_shared and listing_url:
        blast_lines.append(f"Listing/source link: {listing_url}")
    if access_notes:
        blast_lines.append(f"Access/photos note: {access_notes}")
    else:
        blast_lines.append("Access/photos note: photos and access details available internally.")
    if deadline:
        blast_lines.append(f"Buyer response deadline: {deadline}")
    under_contract_blast = "\n".join(blast_lines)

    protected_buyer_message = under_contract_blast if full_blast_allowed and buyer_message_type == "Under-contract buyer blast" else pre_contract_teaser
    warning = "" if full_blast_allowed else DEAL_PROTECTION_WARNING

    return {
        "contract_status": contract_status,
        "deal_protection_mode": protect_mode,
        "address_sharing_level": address_level,
        "listing_source_sharing_level": listing_level,
        "buyer_message_type": buyer_message_type,
        "pre_contract_teaser_message": pre_contract_teaser,
        "under_contract_buyer_blast": under_contract_blast,
        "protected_buyer_message": protected_buyer_message,
        "exact_address_shared": "Yes" if exact_address_shared else "No",
        "protected_fields_hidden": protected_fields_hidden,
        "buyer_message_allowed": buyer_message_allowed,
        "warning": warning,
    }


def clamp_nonnegative(value: float) -> float:
    return max(float(value or 0), 0)


def slow_flip_functional_risks(notes: str) -> list[str]:
    text = str(notes or "").lower()
    risk_terms = {
        "low ceilings": ["low ceiling", "low ceilings", "ceiling height"],
        "no driveway": ["no driveway", "no parking", "shared driveway", "street parking only"],
        "termite damage": ["termite", "termites", "wood destroying", "wdi"],
        "weak rent comps": ["weak rent comp", "weak rent comps", "rent comps weak", "low rent comps", "rent support weak"],
    }
    risks = []
    for label, terms in risk_terms.items():
        if any(term in text for term in terms):
            risks.append(label)
    return risks


def calc_slow_flip(deal: DealInput, a: Assumptions) -> Dict[str, Any]:
    rent = clamp_nonnegative(deal.rent)
    asking = clamp_nonnegative(deal.asking_price)
    arv = clamp_nonnegative(deal.arv)
    repairs = clamp_nonnegative(deal.repairs)

    resale_to_slow_flipper = rent * a.slow_flip_rent_multiple
    rent_formula_max_offer = max(resale_to_slow_flipper - a.min_assignment_fee - a.close_title_buffer, 0)
    value_repair_max_offer = max((arv * 0.65) - repairs - a.min_assignment_fee - a.close_title_buffer, 0) if arv > 0 else 0
    functional_risks = slow_flip_functional_risks(deal.notes)
    risk_adjustment = 0.85 if functional_risks else 1.00
    adjusted_rent_formula_max_offer = rent_formula_max_offer * risk_adjustment
    adjusted_value_repair_max_offer = value_repair_max_offer * risk_adjustment if value_repair_max_offer > 0 else 0
    slow_flip_max_buy_price = clamp_nonnegative(getattr(a, "slow_flip_max_buy_price", 0))
    above_slow_flip_max_buy_price = slow_flip_max_buy_price > 0 and asking > slow_flip_max_buy_price

    # Bradley slow-flip rule: 98% of slow-flip offers stay at or below $32,000.
    # The rent formula still runs, but the public offer/max is capped unless a human approves an exception.
    normal_cap = clamp_nonnegative(getattr(a, "slow_flip_max_offer_cap", 32000))
    max_candidates = [adjusted_rent_formula_max_offer]
    if adjusted_value_repair_max_offer > 0:
        max_candidates.append(adjusted_value_repair_max_offer)
    if normal_cap > 0:
        max_candidates.append(normal_cap)
    if slow_flip_max_buy_price > 0:
        max_candidates.append(slow_flip_max_buy_price)
    max_contract_price = min(max_candidates)

    # Slow flip negotiation rule:
    # The max offer is internal only. We do NOT send the max as the first offer.
    # Normal first offer starts below max, usually $28k when the max is $32k.
    first_offer_gap = clamp_nonnegative(getattr(a, "slow_flip_first_offer_gap", 4000))
    first_offer = max(max_contract_price - first_offer_gap, 0)

    # If the seller is asking below our normal first offer, do not offer above asking.
    offer_to_send = min(first_offer, asking) if asking > 0 else first_offer

    # Internal negotiation band only. Public message still uses one number.
    target_offer_low = offer_to_send
    target_offer_high = max_contract_price

    estimated_fee_at_ask = resale_to_slow_flipper - asking - a.close_title_buffer if asking else 0

    return {
        "exit": "Slow Flip",
        "resale_to_slow_flipper": resale_to_slow_flipper,
        "target_offer_low": target_offer_low,
        "target_offer_high": target_offer_high,
        "first_offer": first_offer,
        "offer_to_send": offer_to_send,
        "max_offer": max_contract_price,
        "rent_formula_max_offer_before_cap": rent_formula_max_offer,
        "risk_adjusted_rent_formula_max_offer": adjusted_rent_formula_max_offer,
        "value_repair_max_offer_before_cap": value_repair_max_offer,
        "risk_adjusted_value_repair_max_offer": adjusted_value_repair_max_offer,
        "normal_slow_flip_cap": normal_cap,
        "slow_flip_max_buy_price": slow_flip_max_buy_price,
        "slow_flip_max_source": getattr(a, "slow_flip_max_source", "Market Default"),
        "above_slow_flip_max_buy_price": above_slow_flip_max_buy_price,
        "functional_risks": functional_risks,
        "estimated_fee_at_ask": estimated_fee_at_ask,
        "spread": resale_to_slow_flipper - asking if asking else resale_to_slow_flipper,
    }


def calc_wholesale(deal: DealInput, a: Assumptions) -> Dict[str, Any]:
    arv = clamp_nonnegative(deal.arv)
    repairs = clamp_nonnegative(deal.repairs)
    asking = clamp_nonnegative(deal.asking_price)

    buyer_target = max((arv * a.wholesale_buyer_percent_arv) - repairs, 0)
    max_contract_price = max(buyer_target - a.min_assignment_fee - a.close_title_buffer, 0)
    target_offer_high = max_contract_price * a.target_offer_discount
    target_offer_low = target_offer_high * 0.90

    # Wholesale uses the low side of the internal target range as the first offer.
    # The max is internal only and should not be shown to agents/sellers.
    first_offer = target_offer_low
    offer_to_send = min(first_offer, asking) if asking > 0 else first_offer

    estimated_fee_at_ask = buyer_target - asking - a.close_title_buffer if asking else 0

    return {
        "exit": "Wholesale",
        "buyer_target": buyer_target,
        "buyer_percent_arv": a.wholesale_buyer_percent_arv,
        "buyer_percent_source": a.wholesale_buyer_percent_source,
        "buyer_percent_range": a.wholesale_buyer_percent_range,
        "buyer_percent_reason": a.wholesale_buyer_percent_reason,
        "market_liquidity_tier": a.market_liquidity_tier,
        "conservative_buyer_target": max((arv * max(a.wholesale_buyer_percent_arv - 0.03, 0.50)) - repairs, 0),
        "aggressive_buyer_target": max((arv * min(a.wholesale_buyer_percent_arv + 0.03, 0.78)) - repairs, 0),
        "market_buyer_percent_arv": a.market_wholesale_buyer_percent,
        "needs_human_review": arv <= 0 or repairs <= 0 or a.wholesale_buyer_percent_arv < 0.55,
        "target_offer_low": target_offer_low,
        "target_offer_high": target_offer_high,
        "first_offer": first_offer,
        "offer_to_send": offer_to_send,
        "max_offer": max_contract_price,
        "estimated_fee_at_ask": estimated_fee_at_ask,
        "spread": buyer_target - asking if asking else buyer_target,
    }


def choose_best_exit(wholesale: Dict[str, Any], slow_flip: Dict[str, Any], deal: DealInput) -> str:
    notes = (deal.notes or "").lower()
    status = (deal.status or "").lower()
    livable = (deal.livable or "").lower()

    if "sold" in status:
        return "Pass"
    if any(word in notes for word in ["fire", "foundation", "condemned", "tear down", "teardown"]):
        return "Needs Human Review"
    if deal.exit_mode == "Slow Flip Only":
        if slow_flip.get("above_slow_flip_max_buy_price") or slow_flip.get("functional_risks"):
            return "Needs Human Review"
        if livable == "no":
            return "Needs Human Review"
        return "Slow Flip" if slow_flip["estimated_fee_at_ask"] >= a_value_min_fee(slow_flip) else "Needs Human Review"
    if deal.exit_mode == "Wholesale Only":
        return "Wholesale" if wholesale["estimated_fee_at_ask"] >= 5000 else "Needs Human Review"

    if (
        deal.rent >= 700
        and slow_flip["estimated_fee_at_ask"] >= 5000
        and livable != "no"
        and not slow_flip.get("above_slow_flip_max_buy_price")
        and not slow_flip.get("functional_risks")
    ):
        return "Slow Flip"
    if wholesale["estimated_fee_at_ask"] >= 5000:
        return "Wholesale"
    return "Needs Human Review"


def a_value_min_fee(result: Dict[str, Any]) -> float:
    return 5000


def grade_deal(best: Dict[str, Any], asking: float, a: Assumptions) -> str:
    fee = best.get("estimated_fee_at_ask", 0)
    max_offer = best.get("max_offer", 0)
    asking = clamp_nonnegative(asking)

    if asking > 0 and max_offer >= asking and fee >= 15000:
        return "A"
    if asking > 0 and max_offer >= asking and fee >= a.min_assignment_fee:
        return "B"
    if asking > 0 and fee >= a.exception_assignment_fee:
        return "C"
    if max_offer > 0:
        return "Review"
    return "Pass"


def risk_notes(deal: DealInput, best_exit: str) -> list[str]:
    risks: list[str] = []
    notes = (deal.notes or "").lower()

    if deal.exit_mode == "Slow Flip Only":
        if deal.rent <= 0:
            risks.append("Missing rent estimate. Pull RentCast before making a slow flip offer.")
        if deal.livable == "No":
            risks.append("Property is not livable. Do not treat this as a clean slow flip without human review.")
        if deal.livable == "Unknown":
            risks.append("Livability is unknown. Confirm utilities, roof, plumbing, HVAC, and whether a buyer could move in quickly.")
    else:
        if deal.arv <= 0:
            risks.append("Missing ARV. Needed only for wholesale analysis.")
        if deal.repairs <= 0 and deal.exit_mode in ["Wholesale Only", "Auto"]:
            risks.append("Repairs are set to $0. Needed only for wholesale analysis.")

    if deal.days_on_market >= 60:
        risks.append("High days on market. Use that as leverage with the agent.")
    if deal.occupancy in ["Tenant occupied", "Owner occupied"]:
        risks.append("Occupied property. Verify access, move-out plan, lease/rent amount, and seller timeline.")
    if any(word in notes for word in ["fire", "foundation", "mold", "moisture", "discoloration", "condemned", "tear down", "teardown"]):
        risks.append("Major condition or moisture red flag. Human review required before offer.")
    if best_exit == "Pass":
        risks.append("Numbers do not support the current asking price. Only proceed if seller shows motivation.")
    if not risks:
        risks.append("No major red flags from the current inputs. Still verify photos, taxes, occupancy, and title issues.")
    return risks


def make_rule_based_message(deal: DealInput, best: Dict[str, Any], grade: str) -> str:
    # Public-facing offer rule:
    # We only give the agent/seller ONE number at a time.
    # The target range and max offer are for internal use only.
    first_offer = money(best.get("offer_to_send", best.get("first_offer", best.get("target_offer_high", 0))))

    if grade in ["Pass", "Review"]:
        return (
            "I would not send a firm offer yet. Send this instead:\n\n"
            "Hey, thanks for the info. Based on where the numbers look right now, we may be a little far apart. "
            "Do you know if the seller has any flexibility, or are they firm on price?"
        )

    if deal.lead_type == "Agent":
        return (
            "Agent message:\n\n"
            f"Hey, thanks for the info. Based on the rent and where we would need to be as cash buyers, "
            f"we could offer {first_offer} cash, as-is, subject to clean title and final walkthrough. "
            "We can keep it simple for the seller. Would you be able to present that?"
        )

    return (
        "Seller message:\n\n"
        f"Thanks for the details. Based on the rent and what we would need to make the numbers work, "
        f"we could offer {first_offer} cash, as-is, subject to clean title and final walkthrough. "
        "Is that something you would want me to write up?"
    )


def analyze_deal(deal: DealInput, assumptions: Assumptions | None = None) -> Dict[str, Any]:
    a = assumptions or Assumptions()
    wholesale = calc_wholesale(deal, a)
    slow_flip = calc_slow_flip(deal, a)

    if deal.exit_mode == "Slow Flip Only":
        best_exit = (
            "Slow Flip"
            if (
                deal.livable != "No"
                and not slow_flip.get("above_slow_flip_max_buy_price")
                and not slow_flip.get("functional_risks")
                and slow_flip["estimated_fee_at_ask"] >= a.exception_assignment_fee
            )
            else "Needs Human Review"
        )
    elif deal.exit_mode == "Wholesale Only":
        if wholesale.get("needs_human_review"):
            best_exit = "Needs Human Review"
        else:
            best_exit = "Wholesale" if wholesale["estimated_fee_at_ask"] >= a.exception_assignment_fee else "Needs Human Review"
    else:
        best_exit = choose_best_exit(wholesale, slow_flip, deal)
        if best_exit == "Wholesale" and wholesale.get("needs_human_review"):
            best_exit = "Needs Human Review"

    if best_exit == "Wholesale":
        best = wholesale
    elif best_exit == "Slow Flip":
        best = slow_flip
    else:
        best = slow_flip if deal.exit_mode == "Slow Flip Only" else wholesale
        best = dict(best)
        best["exit"] = best_exit

    grade = grade_deal(best, deal.asking_price, a) if best_exit != "Pass" else "Pass"
    risks = risk_notes(deal, best_exit)

    if slow_flip.get("above_slow_flip_max_buy_price") and deal.exit_mode in ["Slow Flip Only", "Auto"] and best_exit != "Wholesale":
        risks.insert(0, f"Above Slow Flip Max Buy Price. Buy price is above the slow-flip max buy price of {money(slow_flip.get('slow_flip_max_buy_price', 0))}. Lean human review or pass unless rent/payment/ARV strongly supports the exception.")
    if slow_flip.get("functional_risks") and deal.exit_mode in ["Slow Flip Only", "Auto"] and best_exit != "Wholesale":
        risks.insert(0, "Slow flip functional risk: " + ", ".join(slow_flip.get("functional_risks", [])) + ". Push offer lower and require human review.")
    if wholesale.get("buyer_percent_arv", 1) < 0.55 and deal.exit_mode in ["Wholesale Only", "Auto"]:
        risks.insert(0, "Wholesale buyer percent is below 55%. Require human review before making this a buy decision.")
    if best.get("exit") == "Slow Flip" and deal.asking_price > best.get("max_offer", 0) > 0:
        risks.insert(0, f"Asking price is above the normal slow-flip max of {money(best.get('max_offer', 0))}. Do not chase unless there is a pre-committed buyer or Shawn/Sabrina approves the exception.")
    if best.get("exit") == "Slow Flip" and best.get("rent_formula_max_offer_before_cap", 0) > best.get("max_offer", 0):
        risks.append(f"Rent formula supports up to {money(best.get('rent_formula_max_offer_before_cap', 0))}, but the Bradley slow-flip cap holds the max at {money(best.get('max_offer', 0))}.")
    if best.get("exit") == "Slow Flip" and best.get("offer_to_send", 0) > 0 and best.get("max_offer", 0) > best.get("offer_to_send", 0):
        risks.append(f"Negotiation rule: first offer is {money(best.get('offer_to_send', 0))}. Keep the {money(best.get('max_offer', 0))} max internal and do not reveal it to the agent/seller.")
    message = make_rule_based_message(deal, best, grade)

    return {
        "deal": asdict(deal),
        "assumptions": asdict(a),
        "grade": grade,
        "best_exit": best_exit,
        "best": best,
        "wholesale": wholesale,
        "slow_flip": slow_flip,
        "risks": risks,
        "suggested_message": message,
    }

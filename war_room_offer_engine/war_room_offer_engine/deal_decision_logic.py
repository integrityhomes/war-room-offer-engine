from __future__ import annotations

from typing import Any

AUTO = "Auto — Choose Best"
SLOW_KEEP = "Slow Flip — Keep"
SLOW_WHOLESALE = "Slow Flip — Wholesale"
WHOLESALE_MLS = "Wholesale — MLS"
WHOLESALE_OFF_MARKET = "Wholesale — Off-Market"
STRATEGIES = [AUTO, SLOW_KEEP, SLOW_WHOLESALE, WHOLESALE_MLS, WHOLESALE_OFF_MARKET]
NEGOTIATION_STATUSES = [
    "Not contacted", "Offer ready", "Offer sent", "Counter received", "Negotiating",
    "Verbal agreement", "Contract sent", "Under contract", "Rejected", "Dead lead",
]
MAJOR_TERMS = [
    "foundation failure", "structural failure", "roof collapse", "fire damage", "condemned",
    "unsafe electrical", "no working plumbing", "no electricity", "septic failure",
    "sewer failure", "major water intrusion", "active flooding",
]


def number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value if value not in [None, ""] else default)
    except Exception:
        return default


def money(value: Any) -> str:
    return f"${number(value):,.0f}"


def assumption(a: Any, name: str, default: float) -> float:
    return number(a.get(name), default) if isinstance(a, dict) else number(getattr(a, name, default), default)


def positive_min(*values: Any) -> float:
    values = [number(v) for v in values if number(v) > 0]
    return min(values) if values else 0.0


def is_slow(strategy: str) -> bool:
    return strategy in [SLOW_KEEP, SLOW_WHOLESALE]


def exit_mode(strategy: str) -> str:
    if is_slow(strategy):
        return "Slow Flip Only"
    if strategy in [WHOLESALE_MLS, WHOLESALE_OFF_MARKET]:
        return "Wholesale Only"
    return "Auto"


def source_settings(source: str, strategy: str) -> tuple[str, str, str, str]:
    text = f"{source} {strategy}".lower()
    if any(x in text for x in ["off-market", "xleads", "seller", "cold"]):
        return "Off-Market / Manual", "Off-Market Seller", "Off-market seller lead", "Seller call"
    if "mls" in text or "agent" in text:
        return "Zillow / Sheet Match", "MLS / Agent", "Agent / MLS lead", "MLS"
    return "Zillow / Sheet Match", "Zillow / Apify", "On-market listing", "Zillow"


def current_price(s: dict[str, Any]) -> tuple[float, str]:
    for key, label in [
        ("decision_current_negotiated_price", "Current negotiated price"),
        ("decision_latest_counter", "Latest counter"),
        ("decision_seller_bottom_line", "Seller bottom line"),
        ("contract_price", "Contract / negotiated price"),
        ("decision_asking_price", "Seller asking price"),
        ("asking_price", "Imported asking price"),
    ]:
        value = number(s.get(key))
        if value > 0:
            return value, label
    return 0.0, "Missing price"


def review_flags(s: dict[str, Any]) -> list[str]:
    text = " ".join(str(s.get(k, "") or "") for k in [
        "notes", "repair_notes", "manual_repair_notes", "seller_condition_notes",
        "decision_negotiation_notes", "decision_other_terms",
    ]).lower()
    flags = [term for term in MAJOR_TERMS if term in text]
    if str(s.get("livable", "Unknown")) == "No":
        flags.append("not livable now")
    return list(dict.fromkeys(flags))


def _list_count(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def _normalized_data(s: dict[str, Any]) -> dict[str, Any]:
    normalized = s.get("one_load_normalized", {}) or {}
    data = normalized.get("data", {}) if isinstance(normalized, dict) else {}
    return data if isinstance(data, dict) else {}


def rent_comp_count(s: dict[str, Any]) -> int:
    data = _normalized_data(s)
    return max(
        int(number(s.get("rentcast_rent_comp_count"))),
        int(number(s.get("rentcast_comp_count"))),
        int(number(s.get("rent_comp_count"))),
        int(number(s.get("manual_rent_comp_count"))),
        int(number(data.get("rent_comp_count"))),
        _list_count(s.get("rentcast_rent_comps")),
        _list_count(s.get("rent_comps")),
        _list_count(data.get("rent_comps")),
    )


def rent_verified(s: dict[str, Any]) -> bool:
    count = rent_comp_count(s)
    confidence = str(s.get("rent_confidence", "") or _normalized_data(s).get("rent_confidence", "")).lower()
    has_verified_comps = count >= 3 or "strong" in confidence or "medium" in confidence
    # A stale verification flag must not override actual RentCast comps returned in
    # the same run. Three or more comparable rentals are treated as verified.
    verification_needed = str(s.get("rent_verification_needed", "Yes"))
    return number(s.get("rent") or _normalized_data(s).get("rent")) > 0 and has_verified_comps and (
        verification_needed != "Yes" or count >= 3
    )


def sold_count(s: dict[str, Any]) -> int:
    data = _normalized_data(s)
    return max(
        int(number(s.get("rentcast_value_comp_count"))),
        int(number(s.get("rentcast_sold_comp_count"))),
        int(number(s.get("auto_comp_count"))),
        int(number(data.get("rentcast_sold_comp_count"))),
        _list_count(s.get("rentcast_sold_comps")),
        _list_count(s.get("auto_sold_comps")),
        _list_count(data.get("rentcast_sold_comps")),
        int(number(s.get("strong_comp_count"))) + int(number(s.get("good_comp_count"))),
    )


def slow_terms(s: dict[str, Any], a: Any, keep: bool) -> dict[str, Any]:
    rent = number(s.get("rent"))
    multiple = assumption(a, "slow_flip_rent_multiple", 45)
    fee = assumption(a, "min_assignment_fee", 10000)
    buffer = assumption(a, "close_title_buffer", 1500)
    cap = assumption(a, "slow_flip_max_offer_cap", 32000)
    gap = assumption(a, "slow_flip_first_offer_gap", 4000)
    market_max = number(s.get("slow_flip_max_buy_price_used")) or assumption(a, "slow_flip_max_buy_price", 0)
    resale = rent * multiple
    rent_max = max(resale - buffer - (0 if keep else fee), 0)
    hard_max = positive_min(rent_max, cap, market_max)
    first = max(hard_max - gap, 0)
    asking = number(s.get("decision_asking_price")) or number(s.get("asking_price"))
    if asking > 0 and first > 0:
        first = min(first, asking)
    price, price_source = current_price(s)
    return {
        "hard_max": hard_max, "first_offer": first, "price": price, "price_source": price_source,
        "projected_margin": max(resale - price - buffer, 0) if price > 0 else 0,
        "margin_label": "Gross owner-finance spread" if keep else "Projected slow-flip assignment",
        "exit_value": resale, "exit_value_label": "Owner-finance resale support" if keep else "Slow-flipper resale target",
        "formula": f"{money(rent)} × {multiple:g} = {money(resale)}; less {money(buffer)} buffer" +
                   ("; no assignment fee deducted because the note is kept." if keep else f" and {money(fee)} assignment target."),
    }


def wholesale_terms(s: dict[str, Any], a: Any, engine: dict[str, Any]) -> dict[str, Any]:
    w = (engine or {}).get("wholesale", {})
    buffer = assumption(a, "close_title_buffer", 1500)
    fee = assumption(a, "min_assignment_fee", 10000)
    price, price_source = current_price(s)
    target = number(w.get("buyer_target"))
    return {
        "hard_max": number(w.get("max_offer")),
        "first_offer": number(w.get("offer_to_send")) or number(w.get("first_offer")),
        "price": price, "price_source": price_source,
        "projected_margin": max(target - price - buffer, 0) if price > 0 else 0,
        "margin_label": "Projected assignment", "exit_value": target, "exit_value_label": "Wholesale buyer target",
        "formula": f"Wholesale uses ARV, repairs, buyer percentage, {money(fee)} assignment target, and {money(buffer)} buffer.",
    }


def missing_items(s: dict[str, Any], strategy: str) -> list[str]:
    missing: list[str] = []
    if not str(s.get("address", "") or s.get("decision_property_input", "")).strip():
        missing.append("property address")
    if is_slow(strategy):
        if number(s.get("rent")) <= 0:
            missing.append("rent estimate")
        if not rent_verified(s):
            missing.append("verified rental comps")
    else:
        if number(s.get("arv")) <= 0:
            missing.append("ARV / value")
        confidence = str(s.get("arv_confidence", "Not enough data")).lower()
        if sold_count(s) < 1 and confidence in ["", "weak", "not enough data", "avm only"]:
            missing.append("sold comps / verified ARV")
        if number(s.get("repairs")) <= 0 and str(s.get("repair_source", "Missing")) == "Missing" and not str(s.get("repair_notes", "")).strip():
            missing.append("repair scope")
    return list(dict.fromkeys(missing))


def evaluate(s: dict[str, Any], a: Any, engine: dict[str, Any], strategy: str) -> dict[str, Any]:
    terms = slow_terms(s, a, strategy == SLOW_KEEP) if is_slow(strategy) else wholesale_terms(s, a, engine)
    price, maximum, margin = number(terms["price"]), number(terms["hard_max"]), number(terms["projected_margin"])
    missing, flags = missing_items(s, strategy), review_flags(s)
    normal_fee, exception_fee = assumption(a, "min_assignment_fee", 10000), assumption(a, "exception_assignment_fee", 5000)
    if price <= 0:
        decision, reason = "HUMAN REVIEW", "A current seller price is required."
    elif maximum <= 0:
        decision, reason = ("HUMAN REVIEW", "Missing data prevents a safe maximum.") if missing else ("DO NOT BUY", "The numbers support no positive purchase price.")
    elif price > maximum:
        decision, reason = "DO NOT BUY", f"Current price is {money(price - maximum)} above the maximum."
    elif missing or flags:
        decision, reason = "HUMAN REVIEW", "Price works, but required data or a major condition item still needs verification."
    elif strategy != SLOW_KEEP and margin < normal_fee:
        decision = "HUMAN REVIEW" if margin >= exception_fee else "DO NOT BUY"
        reason = f"Projected assignment is {money(margin)}; normal minimum is {money(normal_fee)}."
    else:
        decision, reason = "BUY", "Current price is within the maximum and the selected exit is supported."
    room = maximum - price if maximum > 0 and price > 0 else 0
    if decision == "BUY":
        next_action = "Confirm title and walkthrough conditions, then move to contract." if s.get("decision_current_negotiated_price") else f"Start at {money(terms['first_offer'])}; do not exceed {money(maximum)}."
    elif decision == "DO NOT BUY":
        next_action = f"Counter at or below {money(maximum)} or pass."
    else:
        next_action = "Verify the missing or flagged information before committing."
    return {**terms, "strategy": strategy, "decision": decision, "reason": reason, "next_action": next_action,
            "missing": missing, "review_flags": flags, "room_left": room, "seller_drop_needed": max(price - maximum, 0) if maximum > 0 else 0}


def build_decision(s: dict[str, Any], a: Any, engine: dict[str, Any], selected: str) -> dict[str, Any]:
    rows = [evaluate(s, a, engine, x) for x in [SLOW_KEEP, SLOW_WHOLESALE, WHOLESALE_MLS, WHOLESALE_OFF_MARKET]]
    by_name = {row["strategy"]: row for row in rows}
    if selected != AUTO:
        chosen = by_name[selected]
    else:
        source = f"{s.get('decision_lead_source', '')} {s.get('source_mode', '')}".lower()
        wholesale = WHOLESALE_OFF_MARKET if any(x in source for x in ["off-market", "seller", "xleads", "cold"]) else WHOLESALE_MLS
        candidates = [by_name[SLOW_KEEP], by_name[SLOW_WHOLESALE], by_name[wholesale]]
        rank = {"BUY": 3, "HUMAN REVIEW": 2, "DO NOT BUY": 1}
        priority = {SLOW_KEEP: 3, SLOW_WHOLESALE: 2, wholesale: 1}
        chosen = max(candidates, key=lambda r: (rank.get(r["decision"], 0), number(r["projected_margin"]), priority.get(r["strategy"], 0)))
    chosen = dict(chosen)
    points = (2 if rent_verified(s) else 0) + (2 if sold_count(s) >= 3 else 1 if sold_count(s) else 0) + (1 if number(s.get("arv")) > 0 else 0) + (1 if not chosen["missing"] and not chosen["review_flags"] else 0)
    chosen["confidence"] = "Weak" if chosen["decision"] == "HUMAN REVIEW" else "Strong" if points >= 5 else "Medium" if points >= 3 else "Weak"
    chosen["evaluations"] = rows
    return chosen

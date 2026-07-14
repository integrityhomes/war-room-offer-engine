from __future__ import annotations

from dataclasses import dataclass
from typing import Any


STRATEGIES = [
    "Slow Flip — Keep",
    "Slow Flip — Wholesale",
    "Wholesale — MLS",
    "Wholesale — Off-Market",
    "Auto — Best Exit",
]

NEGOTIATION_STATUSES = [
    "Not contacted",
    "Ready to make first offer",
    "First offer sent",
    "Seller countered",
    "Negotiating",
    "Verbal agreement",
    "Under contract",
    "Passed",
]


def number(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def money(value: Any) -> str:
    return f"${number(value):,.0f}"


def exit_mode_for_strategy(strategy: str) -> str:
    if str(strategy or "").startswith("Slow Flip"):
        return "Slow Flip Only"
    if str(strategy or "").startswith("Wholesale"):
        return "Wholesale Only"
    return "Auto"


def source_mode_for_strategy(strategy: str) -> tuple[str, str, str]:
    if strategy == "Wholesale — Off-Market":
        return "Off-Market / Manual", "Off-Market Seller", "Off-market seller lead"
    if strategy == "Wholesale — MLS":
        return "Zillow / Sheet Match", "MLS / Agent", "Agent / MLS lead"
    if strategy in ["Slow Flip — Keep", "Slow Flip — Wholesale"]:
        return "Zillow / Sheet Match", "Zillow / Apify", "On-market listing"
    return "Zillow / Sheet Match", "Zillow / Apify", "On-market listing"


def is_slow_flip(strategy: str) -> bool:
    return str(strategy or "").startswith("Slow Flip")


def is_wholesale(strategy: str) -> bool:
    return str(strategy or "").startswith("Wholesale")


def is_keep_slow_flip(strategy: str) -> bool:
    return strategy == "Slow Flip — Keep"


def is_slow_flip_wholesale(strategy: str) -> bool:
    return strategy == "Slow Flip — Wholesale"


def current_price(state: dict[str, Any]) -> float:
    return (
        number(state.get("simple_negotiated_price"))
        or number(state.get("contract_price"))
        or number(state.get("asking_price"))
        or number(state.get("simple_asking_price"))
    )


def asking_price(state: dict[str, Any]) -> float:
    return number(state.get("asking_price")) or number(state.get("simple_asking_price"))


def _positive_min(*values: float) -> float:
    positives = [number(value) for value in values if number(value) > 0]
    return min(positives) if positives else 0.0


def slow_flip_terms(state: dict[str, Any], strategy: str) -> dict[str, Any]:
    rent = number(state.get("rent"))
    rent_multiple = number(state.get("slow_flip_rent_multiple_snapshot")) or 45
    assignment_fee = number(state.get("min_assignment_fee_snapshot")) or 10000
    close_buffer = number(state.get("close_title_buffer_snapshot")) or 1500
    normal_cap = number(state.get("slow_flip_max_offer_cap_snapshot")) or 32000
    first_offer_gap = number(state.get("slow_flip_first_offer_gap_snapshot")) or 4000
    market_max = number(state.get("slow_flip_max_buy_price_used"))
    supported_resale = rent * rent_multiple

    if is_keep_slow_flip(strategy):
        rent_supported_max = max(supported_resale - close_buffer, 0)
        assignment_deduction = 0
    else:
        rent_supported_max = max(supported_resale - assignment_fee - close_buffer, 0)
        assignment_deduction = assignment_fee

    hard_max = _positive_min(rent_supported_max, normal_cap, market_max)
    first_offer = max(hard_max - first_offer_gap, 0)
    ask = asking_price(state)
    if ask > 0:
        first_offer = min(first_offer, ask)

    price = current_price(state)
    gross_spread = max(supported_resale - price - close_buffer, 0) if price > 0 else 0
    if is_keep_slow_flip(strategy):
        margin_label = "Supported spread before financing/holding costs"
        projected_margin = gross_spread
    else:
        margin_label = "Projected slow-flip wholesale fee"
        projected_margin = gross_spread

    return {
        "supported_resale": supported_resale,
        "rent_supported_max": rent_supported_max,
        "normal_cap": normal_cap,
        "market_max": market_max,
        "hard_max": hard_max,
        "first_offer": first_offer,
        "assignment_deduction": assignment_deduction,
        "projected_margin": projected_margin,
        "margin_label": margin_label,
        "formula": (
            f"{money(rent)} monthly support × {rent_multiple:g} = {money(supported_resale)} supported resale; "
            f"less {money(close_buffer)} closing/title buffer"
            + (f" and {money(assignment_fee)} target fee" if assignment_deduction else "")
            + f"; then limited by the normal {money(normal_cap)} slow-flip cap"
            + (f" and {money(market_max)} market maximum" if market_max > 0 else "")
            + "."
        ),
    }


def wholesale_terms(state: dict[str, Any], normalized: dict[str, Any]) -> dict[str, Any]:
    engine_hard_max = number(normalized.get("do_not_exceed")) or number(normalized.get("internal_max"))
    engine_first_offer = number(normalized.get("first_offer"))
    assignment_fee = number(state.get("min_assignment_fee_snapshot")) or 10000
    close_buffer = number(state.get("close_title_buffer_snapshot")) or 1500
    price = current_price(state)
    implied_buyer_target = engine_hard_max + assignment_fee + close_buffer if engine_hard_max > 0 else 0
    projected_fee = max(implied_buyer_target - price - close_buffer, 0) if price > 0 else 0
    return {
        "hard_max": engine_hard_max,
        "first_offer": engine_first_offer,
        "projected_margin": projected_fee,
        "margin_label": "Projected assignment fee at current price",
        "buyer_target": implied_buyer_target,
        "formula": (
            f"The existing wholesale engine uses ARV, buyer percentage, repairs, the {money(assignment_fee)} minimum fee, "
            f"and a {money(close_buffer)} closing/title buffer."
        ),
    }


def strategy_terms(state: dict[str, Any], normalized: dict[str, Any], strategy: str) -> dict[str, Any]:
    if is_slow_flip(strategy):
        return slow_flip_terms(state, strategy)
    return wholesale_terms(state, normalized)


def negotiation_position(state: dict[str, Any], normalized: dict[str, Any], strategy: str) -> dict[str, Any]:
    terms = strategy_terms(state, normalized, strategy)
    hard_max = number(terms.get("hard_max"))
    first_offer = number(terms.get("first_offer"))
    ask = asking_price(state)
    negotiated = number(state.get("simple_negotiated_price")) or number(state.get("contract_price"))
    price_to_test = negotiated or ask
    room_left = hard_max - price_to_test if hard_max > 0 and price_to_test > 0 else 0

    if hard_max <= 0:
        next_action = "Do not buy until the missing data produces a usable maximum price."
        position = "No usable offer range"
    elif negotiated > 0 and negotiated <= hard_max:
        next_action = "The negotiated price is inside the buy box. Confirm final risks and move to contract."
        position = "Inside buy box"
    elif negotiated > hard_max > 0:
        next_action = f"Counter at or below {money(hard_max)}. The seller must drop another {money(negotiated - hard_max)}."
        position = "Above maximum"
    elif ask > hard_max > 0:
        next_action = f"Start at {money(first_offer)} and hold the line at {money(hard_max)}."
        position = "Needs negotiation"
    else:
        next_action = f"Start at {money(first_offer)}. The current price is already within the modeled range."
        position = "Ready for offer"

    return {
        **terms,
        "asking_price": ask,
        "negotiated_price": negotiated,
        "price_tested": price_to_test,
        "room_left": room_left,
        "seller_drop_needed": max(price_to_test - hard_max, 0) if hard_max > 0 else 0,
        "position": position,
        "next_action": next_action,
    }

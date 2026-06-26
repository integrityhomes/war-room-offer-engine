from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Any


@dataclass
class Assumptions:
    min_assignment_fee: float = 10000
    discounted_assignment_fee: float = 5000
    wholesale_buyer_percent_arv: float = 0.70
    slow_flip_rent_multiple: float = 45
    slow_flip_repair_factor: float = 0.50
    cash_close_buffer: float = 1500
    target_offer_discount: float = 0.85


@dataclass
class DealInput:
    address: str
    market: str
    lead_type: str
    asking_price: float
    arv: float
    repairs: float
    rent: float
    beds: float
    baths: float
    sqft: float
    taxes: float
    status: str
    days_on_market: int
    notes: str


def money(value: float) -> str:
    try:
        return "${:,.0f}".format(float(value))
    except Exception:
        return "$0"


def clamp_nonnegative(value: float) -> float:
    return max(float(value or 0), 0)


def calc_wholesale(deal: DealInput, a: Assumptions) -> Dict[str, Any]:
    arv = clamp_nonnegative(deal.arv)
    repairs = clamp_nonnegative(deal.repairs)
    asking = clamp_nonnegative(deal.asking_price)

    buyer_target = max((arv * a.wholesale_buyer_percent_arv) - repairs, 0)
    max_offer = max(buyer_target - a.min_assignment_fee - a.cash_close_buffer, 0)
    target_offer = max_offer * a.target_offer_discount

    if asking > 0:
        est_fee_at_ask = buyer_target - asking - a.cash_close_buffer
    else:
        est_fee_at_ask = buyer_target - max_offer - a.cash_close_buffer

    return {
        "exit": "Wholesale",
        "buyer_target": buyer_target,
        "target_offer_low": target_offer * 0.90,
        "target_offer_high": target_offer,
        "max_offer": max_offer,
        "estimated_fee_at_ask": est_fee_at_ask,
        "spread": buyer_target - asking if asking else buyer_target,
    }


def calc_slow_flip(deal: DealInput, a: Assumptions) -> Dict[str, Any]:
    rent = clamp_nonnegative(deal.rent)
    asking = clamp_nonnegative(deal.asking_price)
    repairs = clamp_nonnegative(deal.repairs)

    resale_to_slow_flipper = rent * a.slow_flip_rent_multiple
    repair_credit = repairs * a.slow_flip_repair_factor
    max_offer = max(resale_to_slow_flipper - a.min_assignment_fee - repair_credit - a.cash_close_buffer, 0)
    target_offer = max_offer * a.target_offer_discount

    if asking > 0:
        est_fee_at_ask = resale_to_slow_flipper - asking - repair_credit - a.cash_close_buffer
    else:
        est_fee_at_ask = resale_to_slow_flipper - max_offer - repair_credit - a.cash_close_buffer

    return {
        "exit": "Slow Flip",
        "resale_to_slow_flipper": resale_to_slow_flipper,
        "repair_credit": repair_credit,
        "target_offer_low": target_offer * 0.90,
        "target_offer_high": target_offer,
        "max_offer": max_offer,
        "estimated_fee_at_ask": est_fee_at_ask,
        "spread": resale_to_slow_flipper - asking if asking else resale_to_slow_flipper,
    }


def choose_best_exit(wholesale: Dict[str, Any], slow_flip: Dict[str, Any], deal: DealInput) -> str:
    notes = (deal.notes or "").lower()
    status = (deal.status or "").lower()

    if any(word in notes for word in ["fire", "foundation", "condemned", "tear down", "teardown"]):
        return "Needs Human Review"

    if "sold" in status:
        return "Pass"

    wholesale_fee = wholesale["estimated_fee_at_ask"]
    slow_fee = slow_flip["estimated_fee_at_ask"]

    # User's business likes slow flips when rent supports the property and acquisition is low.
    if deal.rent >= 750 and deal.asking_price <= 55000 and slow_fee >= 5000:
        return "Slow Flip"

    if wholesale_fee >= slow_fee and wholesale_fee >= 5000:
        return "Wholesale"

    if slow_fee >= 5000:
        return "Slow Flip"

    if max(wholesale["max_offer"], slow_flip["max_offer"]) > 0:
        return "Needs Human Review"

    return "Pass"


def grade_deal(best: Dict[str, Any], asking: float, a: Assumptions) -> str:
    fee = best.get("estimated_fee_at_ask", 0)
    max_offer = best.get("max_offer", 0)
    asking = clamp_nonnegative(asking)

    if asking > 0 and max_offer >= asking and fee >= 12000:
        return "A"
    if asking > 0 and max_offer >= asking and fee >= a.min_assignment_fee:
        return "B"
    if fee >= a.discounted_assignment_fee:
        return "C"
    return "Pass"


def risk_notes(deal: DealInput, wholesale: Dict[str, Any], slow_flip: Dict[str, Any], best_exit: str) -> list[str]:
    risks: list[str] = []
    notes = (deal.notes or "").lower()

    if deal.arv <= 0:
        risks.append("Missing ARV. Verify comps before making a firm offer.")
    if deal.rent <= 0:
        risks.append("Missing rent estimate. Pull RentCast before calling this a slow flip.")
    if deal.repairs <= 0:
        risks.append("Repairs are set to $0. Confirm condition from photos or seller notes.")
    if deal.days_on_market >= 60:
        risks.append("High days on market. Use that as leverage with the agent.")
    if any(word in notes for word in ["tenant", "occupied", "rented"]):
        risks.append("Occupied property. Verify lease, rent amount, tenant status, and access.")
    if any(word in notes for word in ["fire", "foundation", "mold", "condemned", "tear down", "teardown"]):
        risks.append("Major condition red flag. Human review required before offer.")
    if best_exit == "Pass":
        risks.append("Numbers do not support the current asking price. Only proceed if seller shows motivation.")
    if not risks:
        risks.append("No major red flags from the current inputs. Still verify photos, title issues, taxes, and occupancy.")
    return risks


def make_rule_based_message(deal: DealInput, best: Dict[str, Any], grade: str) -> str:
    low = money(best["target_offer_low"])
    high = money(best["target_offer_high"])
    max_offer = money(best["max_offer"])
    exit_type = best["exit"]

    if grade == "Pass":
        return (
            "I would not send a firm offer yet. Send this instead:\n\n"
            "Hey, thanks for the info. Based on where the numbers look right now, we may be a little far apart. "
            "Do you know if the seller has any flexibility, or are they firm on price?"
        )

    if deal.lead_type == "Agent":
        return (
            f"Agent message:\n\n"
            f"Hey, thanks for the info. Based on the condition and where we would need to be as cash buyers, "
            f"we would likely be in the {low} to {high} range, with our absolute max around {max_offer} if everything checks out. "
            f"We can buy as-is and keep it simple. Do you think the seller would consider something in that range?"
        )

    return (
        f"Seller message:\n\n"
        f"Thanks for the details. Based on what we know right now, this looks more like a {exit_type.lower()} deal for us. "
        f"We would probably be around {low} to {high} cash, as-is, with our max around {max_offer} if everything checks out. "
        f"Is that close enough for me to keep working on it?"
    )


def analyze_deal(deal: DealInput, assumptions: Assumptions | None = None) -> Dict[str, Any]:
    a = assumptions or Assumptions()
    wholesale = calc_wholesale(deal, a)
    slow_flip = calc_slow_flip(deal, a)
    best_exit = choose_best_exit(wholesale, slow_flip, deal)

    if best_exit == "Wholesale":
        best = wholesale
    elif best_exit == "Slow Flip":
        best = slow_flip
    else:
        # Use strongest numbers for review/pass while preserving label.
        best = wholesale if wholesale["estimated_fee_at_ask"] >= slow_flip["estimated_fee_at_ask"] else slow_flip
        best = dict(best)
        best["exit"] = best_exit

    grade = grade_deal(best, deal.asking_price, a) if best_exit not in ["Pass"] else "Pass"
    risks = risk_notes(deal, wholesale, slow_flip, best_exit)
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

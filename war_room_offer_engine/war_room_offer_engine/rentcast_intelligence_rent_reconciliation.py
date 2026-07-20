from __future__ import annotations

from statistics import median
from typing import Any

try:
    import rentcast_intelligence_core as core
    import rentcast_intelligence_rent_ui_fix as rent_ui
except ImportError:
    try:
        from . import rentcast_intelligence_core as core
        from . import rentcast_intelligence_rent_ui_fix as rent_ui
    except ImportError:
        from war_room_offer_engine import rentcast_intelligence_core as core
        from war_room_offer_engine import rentcast_intelligence_rent_ui_fix as rent_ui


_ORIGINAL_BUILD = getattr(
    rent_ui,
    "_rent_reconciliation_original_build",
    rent_ui.build_rent_display_model,
)


def _has_listing_age(row: dict[str, Any]) -> bool:
    return bool(
        core._clean_text(row.get("listed_date"))
        or core._clean_text(row.get("last_seen_date"))
        or core._clean_text(row.get("removed_date"))
        or core._number(row.get("days_old")) > 0
    )


def _candidate_total(rows: list[dict[str, Any]], quality: dict[str, Any]) -> int:
    scored_total = sum(
        int(core._number(quality.get(key)))
        for key in ("strong", "good", "weak", "excluded")
    )
    return max(len(rows), scored_total)


def _weighted_average(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    weights = [max(int(core._number(row.get("score_points"))), 1) for row in rows]
    denominator = sum(weights)
    if denominator <= 0:
        return 0.0
    return sum(core._number(row.get("rent")) * weight for row, weight in zip(rows, weights)) / denominator


def _search_mode(max_distance: float, max_days: int, missing_age: bool) -> str:
    if not missing_age and max_distance <= 5 and max_days <= 270:
        return "Local"
    if not missing_age and max_distance <= 10 and max_days <= 540:
        return "Expanded"
    if max_distance <= 25:
        return "Rural"
    return "Deep rural"


def build_rent_display_model_reconciled(
    st: Any,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Rebuild visible counts and confidence from the rows the engine selected.

    Legacy widgets can overwrite ``rent_comp_count`` and ``rent_confidence`` with
    the number of displayed rows. This reconciler treats row-level inclusion,
    score, distance, status, and listing age as authoritative so a rural result
    cannot become Strong merely because many distant rows were returned.
    """
    model = dict(_ORIGINAL_BUILD(st, data) or {})
    rows = [dict(row) for row in (model.get("rows", []) or []) if isinstance(row, dict)]
    selected = [row for row in rows if bool(row.get("include_default"))]
    quality = dict(model.get("quality_summary", {}) or {})

    total = _candidate_total(rows, quality)
    used = len(selected)
    verified = sum(row.get("score") in {"Strong Comp", "Good Comp"} for row in selected)
    rents = [core._number(row.get("rent")) for row in selected if core._number(row.get("rent")) > 0]
    comp_median = median(rents) if rents else 0.0
    weighted = _weighted_average(selected)

    distances = [
        core._number(row.get("distance"))
        for row in selected
        if core._optional_number(row.get("distance")) is not None
    ]
    max_distance = max(distances, default=0.0)
    ages = [int(core._number(row.get("days_old"))) for row in selected if core._number(row.get("days_old")) > 0]
    max_days = max(ages, default=0)
    missing_age = bool(selected) and any(not _has_listing_age(row) for row in selected)
    inactive = sum(core._clean_text(row.get("status")).lower() == "inactive" for row in selected)

    avm = core._number(model.get("rentcast_avm"))
    disagreement = (
        abs(comp_median - avm) / ((comp_median + avm) / 2)
        if comp_median > 0 and avm > 0
        else 0.0
    )

    if verified >= 3 and comp_median > 0:
        if avm > 0 and disagreement <= 0.20:
            recommended = 0.65 * comp_median + 0.35 * avm
        elif avm > 0:
            recommended = min(comp_median, avm)
        else:
            recommended = comp_median
    else:
        existing = core._number(model.get("recommended_rent"))
        recommended = min(existing, comp_median) if existing > 0 and comp_median > 0 else existing or comp_median or avm

    reasons = [str(reason) for reason in (model.get("verification_reasons", []) or []) if str(reason).strip()]
    if verified < 3:
        reasons.append("Fewer than three strong or good rental listings support the underwritten rent.")
    if max_distance > 25:
        reasons.append(f"Rental evidence expanded as far as {max_distance:.1f} miles.")
    if missing_age:
        reasons.append("One or more rental listings used in the calculation have no verifiable listing age.")
    if max_days > 730:
        reasons.append(f"Rental evidence includes listings up to {max_days} days old.")
    if selected and inactive == len(selected):
        reasons.append("Only historical inactive rental listings were used.")
    if disagreement > 0.25:
        reasons.append("RentCast AVM and the selected rental-comp median disagree by more than 25%.")
    if not selected and rows:
        reasons.append("No returned rental listing passed the current inclusion rules.")
    reasons = list(dict.fromkeys(reasons))

    requires_review = bool(reasons)
    if (
        verified >= 5
        and max_distance <= 10
        and max_days <= 365
        and not missing_age
        and not requires_review
    ):
        confidence = "Strong verified rent comps"
    elif (
        verified >= 3
        and max_distance <= 25
        and max_days <= 730
        and not missing_age
        and not requires_review
    ):
        confidence = "Medium verified rent comps"
    else:
        confidence = "Weak rural fallback comps" if rows else "AVM only" if avm or recommended else "Missing"

    quality.update(
        {
            "strong": sum(row.get("score") == "Strong Comp" for row in selected),
            "good": sum(row.get("score") == "Good Comp" for row in selected),
            "weak": sum(row.get("score") == "Weak Comp" for row in selected),
            "excluded": max(total - used, 0),
            "displayed": len(rows),
            "candidate_total": total,
            "avm_comp_disagreement_pct": round(disagreement * 100, 1),
            "calculation_comp_quality": (
                "Strong and good rental listings only" if verified >= 3 else "Weak rural fallback"
            ),
        }
    )

    model.update(
        {
            "rows": rows,
            "selected_rows": selected,
            "total_listing_count": total,
            "used_comp_count": used,
            "verified_comp_count": verified,
            "recommended_rent": core._round_money(recommended),
            "comp_average": core._round_money(weighted),
            "comp_median": core._round_money(comp_median),
            "rent_low": core._round_money(core._quantile(rents, 0.25)) if rents else 0,
            "rent_high": core._round_money(core._quantile(rents, 0.75)) if rents else 0,
            "confidence": confidence,
            "requires_human_verification": requires_review,
            "verification_reasons": reasons,
            "search_mode": _search_mode(max_distance, max_days, missing_age),
            "search_radius": round(max_distance, 2),
            "search_days": max_days,
            "quality_summary": quality,
        }
    )
    return model


def install() -> bool:
    if getattr(rent_ui, "_rent_reconciliation_installed", False):
        return True
    rent_ui._rent_reconciliation_original_build = _ORIGINAL_BUILD
    rent_ui.build_rent_display_model = build_rent_display_model_reconciled
    rent_ui._rent_reconciliation_installed = True
    return True


install()

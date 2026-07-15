from __future__ import annotations

import re
from statistics import median
from typing import Any

try:
    import address_rentcast_bridge as bridge
    import rentcast_auto_enrichment as rentcast
    import rentcast_state_bootstrap as bootstrap
    import sold_comps as sold
except ImportError:
    try:
        from . import address_rentcast_bridge as bridge
        from . import rentcast_auto_enrichment as rentcast
        from . import rentcast_state_bootstrap as bootstrap
        from . import sold_comps as sold
    except ImportError:
        from war_room_offer_engine import address_rentcast_bridge as bridge
        from war_room_offer_engine import rentcast_auto_enrichment as rentcast
        from war_room_offer_engine import rentcast_state_bootstrap as bootstrap
        from war_room_offer_engine import sold_comps as sold


_ORIGINAL_ENRICH = rentcast.enrich_property_with_rentcast
_ORIGINAL_BRIDGE_HYDRATE = bridge._hydrate_state
_ORIGINAL_BOOTSTRAP_HYDRATE = bootstrap.hydrate_rentcast_state

_STREET_SUFFIX_PATTERN = re.compile(
    r"^(.*?\b(?:st|rd|dr|ave|ln|ct|blvd|pl|pkwy|hwy|trl|ter|cir|way)\b)",
    re.IGNORECASE,
)


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _street_key(value: Any) -> str:
    """Return a stable street-only key without confusing 115 with 1115."""
    normalized = rentcast._normalize_address(value)
    if not normalized:
        return ""
    comma_part = str(value or "").split(",", 1)[0]
    comma_key = rentcast._normalize_address(comma_part)
    match = _STREET_SUFFIX_PATTERN.match(normalized)
    suffix_key = rentcast._normalize_address(match.group(1)) if match else ""
    return suffix_key or comma_key or normalized


def _is_subject_comp(subject_address: str, comp_address: str) -> bool:
    subject_full = rentcast._normalize_address(subject_address)
    comp_full = rentcast._normalize_address(comp_address)
    if subject_full and comp_full and subject_full == comp_full:
        return True
    subject_street = _street_key(subject_address)
    comp_street = _street_key(comp_address)
    return bool(subject_street and comp_street and subject_street == comp_street)


def _score_label(points: int, flags: list[str]) -> str:
    if points >= 85 and not flags:
        return "Strong Comp"
    if points >= 70:
        return "Good Comp"
    if points >= 45:
        return "Weak Comp"
    return "Bad Comp"


def _critical_exclusion(flags: list[str]) -> bool:
    excluded = {
        "missing sold price",
        "missing sqft",
        "too far away",
        "sqft more than 25% different",
        "different property type",
        "possible distressed sale",
    }
    return any(flag in excluded for flag in flags)


def _score_rentcast_stage(
    comps: list[dict[str, Any]],
    subject: dict[str, Any],
    radius_label: str,
    date_range_label: str,
) -> list[dict[str, Any]]:
    radius = sold.radius_to_float(radius_label)
    scored: list[dict[str, Any]] = []

    for comp in comps:
        row = sold.score_sold_comp(comp, subject, radius, date_range_label)
        flags = list(row.get("flags", []) or [])
        points = int(row.get("score_points", 0) or 0)

        # RentCast's value-comparable payload can omit transaction dates. Keep
        # those records available for a provisional value opinion, but never
        # present them as verified recent sales.
        if "missing sold date" in flags and str(comp.get("source", "")).lower().startswith("rentcast"):
            flags.remove("missing sold date")
            flags.append("sale date unavailable from RentCast; verify before relying on ARV")
            points = min(points + 15, 100)  # retain a 10-point recency penalty

        score = _score_label(points, flags)
        include = score != "Bad Comp" and not _critical_exclusion(flags)
        scored.append(
            {
                **row,
                "flags": sorted(set(flags)),
                "score_points": max(min(points, 100), 0),
                "score": score,
                "include_default": include,
            }
        )

    # Apply a robust median-based outlier check only to otherwise comparable
    # properties. This avoids distant luxury properties distorting the average
    # and incorrectly labeling all normal local comps as low outliers.
    eligible_prices = [
        _number(row.get("sold_price"))
        for row in scored
        if row.get("include_default") and _number(row.get("sold_price")) > 0
    ]
    center = median(eligible_prices) if len(eligible_prices) >= 3 else 0
    if center > 0:
        updated: list[dict[str, Any]] = []
        for row in scored:
            flags = list(row.get("flags", []) or [])
            points = int(row.get("score_points", 0) or 0)
            price = _number(row.get("sold_price"))
            include = bool(row.get("include_default"))
            if include and (price < center * 0.60 or price > center * 1.60):
                flags.append("price outlier versus comparable local properties")
                points -= 25
                include = False
            score = _score_label(points, flags)
            updated.append(
                {
                    **row,
                    "flags": sorted(set(flags)),
                    "score_points": max(points, 0),
                    "score": score,
                    "include_default": include and score != "Bad Comp",
                }
            )
        scored = updated

    return scored


def build_sold_comp_intelligence_fixed(
    data: dict[str, Any],
    sold_comps: list[dict[str, Any]],
    full_address: str = "",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    subject_address = full_address or rentcast.build_full_address(data)
    filtered: list[dict[str, Any]] = []
    removed_subject_count = 0

    for comp in sold_comps or []:
        if not isinstance(comp, dict) or _number(comp.get("sold_price")) <= 0:
            continue
        if _is_subject_comp(subject_address, str(comp.get("comp_address", "") or "")):
            removed_subject_count += 1
            continue
        filtered.append(comp)

    subject = rentcast._comp_subject(data, subject_address)
    candidates: list[tuple[list[dict[str, Any]], dict[str, Any], str, str, tuple[int, ...]]] = []

    for stage_index, (radius, date_range) in enumerate(rentcast.AUTO_COMP_SEARCH_STAGES):
        scored = _score_rentcast_stage(filtered, subject, radius, date_range)
        summary = sold.calculate_arv_from_comps(scored)
        included = [row for row in scored if row.get("include_default") and row.get("score") != "Bad Comp"]
        quality_count = sum(1 for row in included if row.get("score") in ["Strong Comp", "Good Comp"])
        rank = (
            1 if len(included) >= 3 and _number(summary.get("recommended_arv")) > 0 else 0,
            quality_count,
            len(included),
            1 if _number(summary.get("recommended_arv")) > 0 else 0,
            -stage_index,
        )
        candidates.append((scored, summary, radius, date_range, rank))
        if rank[0] == 1:
            break

    if candidates:
        scored, summary, radius, date_range, _ = max(candidates, key=lambda item: item[4])
    else:
        scored, summary, radius, date_range = [], sold.calculate_arv_from_comps([]), "1 mile", "Last 12 months"

    included = [row for row in scored if row.get("include_default") and row.get("score") != "Bad Comp"]
    unverified_dates = any(
        "sale date unavailable from RentCast" in " ".join(str(flag) for flag in row.get("flags", []))
        for row in included
    )

    summary = dict(summary)
    summary.update(
        {
            "search_radius": radius,
            "date_range": date_range,
            "subject_comp_removed_count": removed_subject_count,
            "candidate_comp_count": len(filtered),
            "included_comp_count": len(included),
            "sale_dates_unverified": unverified_dates,
            "comp_data_type": "RentCast value comparables",
        }
    )
    if summary.get("recommended_arv", 0) and unverified_dates:
        summary["arv_confidence"] = "Weak"
        summary["explanation"] = (
            f"Provisional ARV uses {len(included)} nearby RentCast value comparable(s). "
            "RentCast did not provide sale dates, so verify recent closed sales before relying on this ARV."
        )
    return scored, summary


def enrich_property_with_rentcast_fixed(data: dict[str, Any], api_key: str, session=None) -> dict[str, Any]:
    kwargs = {} if session is None else {"session": session}
    enriched = _ORIGINAL_ENRICH(data, api_key, **kwargs)
    summary = enriched.get("auto_arv_summary", {}) or {}
    if summary.get("sale_dates_unverified") and _number(summary.get("recommended_arv")) > 0:
        enriched["arv"] = _number(summary.get("recommended_arv"))
        enriched["arv_source"] = "RentCast Value Comps — dates unverified"
        enriched["arv_confidence"] = "Weak"
    return enriched


def _rounded_average(values: list[float]) -> int:
    return int((sum(values) / len(values)) + 0.5) if values else 0


def _store_rent_stats(st, result: dict[str, Any] | None = None) -> None:
    result = result or {}
    comps = result.get("rent_comps") or st.session_state.get("rentcast_rent_comps") or st.session_state.get("rent_comps") or []
    rents = [_number(row.get("rent")) for row in comps if isinstance(row, dict) and _number(row.get("rent")) > 0]
    average = _number(result.get("rent_comp_average")) or _rounded_average(rents)
    med = _number(result.get("rent_comp_median")) or (int(median(rents) + 0.5) if rents else 0)
    for key in ["rent_comp_average", "rentcast_rent_comp_average"]:
        st.session_state[key] = int(average) if average > 0 else 0
    for key in ["rent_comp_median", "rentcast_rent_comp_median"]:
        st.session_state[key] = int(med) if med > 0 else 0


def _store_unverified_source(st, result: dict[str, Any] | None = None) -> None:
    result = result or {}
    summary = result.get("auto_arv_summary") or st.session_state.get("auto_arv_summary") or {}
    if summary.get("sale_dates_unverified") and _number(summary.get("recommended_arv")) > 0:
        st.session_state["arv"] = int(_number(summary.get("recommended_arv")))
        st.session_state["arv_source_used"] = "RentCast Value Comps — dates unverified"
        st.session_state["value_source"] = "RentCast Value Comps — dates unverified"
        st.session_state["arv_confidence"] = "Weak"
        st.session_state["arv_fallback_reason"] = summary.get("explanation", "RentCast comp dates require verification.")


def bridge_hydrate_fixed(result: dict[str, Any]) -> None:
    _ORIGINAL_BRIDGE_HYDRATE(result)
    try:
        import streamlit as st
    except Exception:
        return
    _store_rent_stats(st, result)
    _store_unverified_source(st, result)


def bootstrap_hydrate_fixed(st) -> None:
    _ORIGINAL_BOOTSTRAP_HYDRATE(st)
    normalized = st.session_state.get("one_load_normalized", {}) or {}
    data = normalized.get("data", {}) if isinstance(normalized, dict) else {}
    last_pull = st.session_state.get("last_auto_pull", {}) or {}
    source = data if isinstance(data, dict) and data else last_pull if isinstance(last_pull, dict) else {}
    _store_rent_stats(st, source)
    _store_unverified_source(st, source)


def install() -> bool:
    if getattr(rentcast, "_rentcast_comp_normalization_fix_installed", False):
        return True
    rentcast.build_sold_comp_intelligence = build_sold_comp_intelligence_fixed
    rentcast.enrich_property_with_rentcast = enrich_property_with_rentcast_fixed
    bridge.enrich_property_with_rentcast = enrich_property_with_rentcast_fixed
    bridge._hydrate_state = bridge_hydrate_fixed
    bootstrap.build_sold_comp_intelligence = build_sold_comp_intelligence_fixed
    bootstrap.hydrate_rentcast_state = bootstrap_hydrate_fixed
    rentcast._rentcast_comp_normalization_fix_installed = True
    return True


install()

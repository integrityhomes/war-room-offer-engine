from __future__ import annotations

import copy
from typing import Any

try:
    import rentcast_intelligence_core as core
    import rentcast_intelligence_preview as preview
    import rentcast_rural_rental_scoring as rent_scoring
    from ui_sections import rent_fallback_ui
except ImportError:
    try:
        from . import rentcast_intelligence_core as core
        from . import rentcast_intelligence_preview as preview
        from . import rentcast_rural_rental_scoring as rent_scoring
        from .ui_sections import rent_fallback_ui
    except ImportError:
        from war_room_offer_engine import rentcast_intelligence_core as core
        from war_room_offer_engine import rentcast_intelligence_preview as preview
        from war_room_offer_engine import rentcast_rural_rental_scoring as rent_scoring
        from war_room_offer_engine.ui_sections import rent_fallback_ui


_ORIGINAL_RENDER = getattr(
    rent_fallback_ui,
    "_rural_rent_ui_original_render",
    rent_fallback_ui.render_rent_fallback_section,
)
_ORIGINAL_SCORE = getattr(
    rent_scoring,
    "_rural_rent_ui_original_score",
    rent_scoring._score_rent_comp,
)

_INTELLIGENCE_KEYS = (
    "rent",
    "rent_estimate",
    "rent_source",
    "rent_confidence",
    "rent_verification_needed",
    "rent_comps",
    "rent_comp_count",
    "rent_comp_average",
    "rent_comp_median",
    "rent_low",
    "rent_high",
    "rentcast_rent_avm",
    "verified_rent_comp_count",
    "rent_search_mode",
    "rent_search_radius",
    "rent_search_days",
    "rent_search_trail",
    "rent_requires_human_verification",
    "rent_verification_reasons",
    "rent_comp_quality_summary",
    "rural_market_detected",
    "rentcast_submitted_address",
)


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on", "required"}


def _intelligence_data(st: Any) -> dict[str, Any]:
    normalized = st.session_state.get("one_load_normalized", {}) or {}
    raw = normalized.get("data", {}) if isinstance(normalized, dict) else {}
    data = dict(raw) if isinstance(raw, dict) else {}
    for key in _INTELLIGENCE_KEYS:
        if key in st.session_state:
            data[key] = copy.deepcopy(st.session_state.get(key))
    if "rent_comps" not in data:
        rows = st.session_state.get("rentcast_rent_comps") or st.session_state.get("rent_comps")
        if isinstance(rows, list):
            data["rent_comps"] = copy.deepcopy(rows)
    return data


def _rent_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    rows = data.get("rent_comps", [])
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, dict) and core._number(row.get("rent")) > 0]


def _rural_preview_active(st: Any, data: dict[str, Any] | None = None) -> bool:
    if not preview.preview_enabled(st):
        return False
    data = data or _intelligence_data(st)
    if any(key in data for key in (
        "verified_rent_comp_count",
        "rent_requires_human_verification",
        "rent_search_mode",
        "rent_comp_quality_summary",
        "rentcast_rent_avm",
    )):
        return True
    return any(
        row.get("record_type") == "rental_listing"
        or str(row.get("source", "")).startswith("RentCast Rental Listing")
        for row in _rent_rows(data)
    )


def score_rent_comp_ui_hardened(
    comp: dict[str, Any], subject: dict[str, Any]
) -> dict[str, Any]:
    """Keep distant, stale, inactive, or materially different listings out of verified counts."""
    row = dict(_ORIGINAL_SCORE(comp, subject) or {})
    if row.get("score") == "Bad Comp":
        return row

    flags = list(row.get("flags", []) or [])
    points = int(row.get("score_points", 0) or 0)
    score_cap = 100
    distance = core._optional_number(row.get("distance"))
    days_old = int(core._number(row.get("days_old"))) if core._number(row.get("days_old")) else 0
    status = core._clean_text(row.get("status")).lower()
    sqft_delta = core._number(row.get("sqft_delta_pct"))

    if distance is not None and distance > 25:
        flags.append("too distant to count as verified rental support")
        score_cap = min(score_cap, 71)
    elif distance is not None and distance > 10:
        flags.append("expanded rural rental evidence")
        score_cap = min(score_cap, 87)

    if status == "inactive":
        flags.append("inactive listing cannot count as verified current rent")
        score_cap = min(score_cap, 71)

    has_age = bool(
        core._clean_text(row.get("listed_date"))
        or core._clean_text(row.get("last_seen_date"))
        or core._clean_text(row.get("removed_date"))
        or days_old > 0
    )
    if not has_age:
        flags.append("listing age could not be verified")
        score_cap = min(score_cap, 71)
    elif days_old > 730:
        flags.append("listing is too old to count as verified current rent")
        score_cap = min(score_cap, 71)

    if sqft_delta > 45:
        flags.append("rental square footage differs materially")
        score_cap = min(score_cap, 71)
    elif sqft_delta > 30:
        flags.append("rental square footage differs by more than 30%")
        score_cap = min(score_cap, 87)

    if any(
        flag in {
            "rental bedroom count differs materially",
            "rental bathroom count differs materially",
        }
        for flag in flags
    ):
        score_cap = min(score_cap, 71)

    points = min(points, score_cap)
    row.update(
        {
            "flags": sorted(set(flags)),
            "score_points": points,
            "score": rent_scoring._score_label(points, False),
        }
    )
    return row


def build_rent_display_model(st: Any, data: dict[str, Any] | None = None) -> dict[str, Any]:
    data = data or _intelligence_data(st)
    rows = _rent_rows(data)
    selected = [row for row in rows if bool(row.get("include_default"))]
    total = len(rows)

    count_present = "rent_comp_count" in data or "rent_comp_count" in st.session_state
    used_count = int(core._number(data.get("rent_comp_count"))) if count_present else len(selected)
    if used_count <= 0 and selected:
        used_count = len(selected)

    verified_present = (
        "verified_rent_comp_count" in data
        or "verified_rent_comp_count" in st.session_state
    )
    verified = (
        int(core._number(data.get("verified_rent_comp_count")))
        if verified_present
        else sum(row.get("score") in {"Strong Comp", "Good Comp"} for row in selected)
    )

    quality = data.get("rent_comp_quality_summary", {})
    quality = dict(quality) if isinstance(quality, dict) else {}
    reasons = data.get("rent_verification_reasons", [])
    reasons = [str(reason) for reason in reasons] if isinstance(reasons, list) else []
    requires_review = _as_bool(data.get("rent_requires_human_verification")) or verified < 3
    if requires_review and not reasons:
        reasons.append("Fewer than three quality rental listings support a binding slow-flip decision.")

    recommended = core._number(data.get("rent") or data.get("rent_estimate"))
    avm = core._number(data.get("rentcast_rent_avm"))
    confidence = core._clean_text(data.get("rent_confidence")) or (
        "Strong verified rent comps" if verified >= 5 and not requires_review
        else "Medium verified rent comps" if verified >= 3 and not requires_review
        else "Weak rural fallback comps" if rows
        else "AVM only" if avm or recommended
        else "Missing"
    )

    return {
        "rows": rows,
        "selected_rows": selected,
        "total_listing_count": total,
        "used_comp_count": used_count,
        "verified_comp_count": verified,
        "recommended_rent": recommended,
        "rentcast_avm": avm,
        "comp_average": core._number(data.get("rent_comp_average")),
        "comp_median": core._number(data.get("rent_comp_median")),
        "rent_low": core._number(data.get("rent_low")),
        "rent_high": core._number(data.get("rent_high")),
        "confidence": confidence,
        "requires_human_verification": requires_review,
        "verification_reasons": list(dict.fromkeys(reasons)),
        "search_mode": core._clean_text(data.get("rent_search_mode")) or "Adaptive",
        "search_radius": core._number(data.get("rent_search_radius")),
        "search_days": int(core._number(data.get("rent_search_days"))),
        "quality_summary": quality,
        "source": core._clean_text(data.get("rent_source")) or "RentCast rural rental intelligence",
        "submitted_address": core._clean_text(data.get("rentcast_submitted_address")),
    }


def _store_intelligent_rent_state(st: Any, model: dict[str, Any]) -> None:
    state = st.session_state
    rows = copy.deepcopy(model.get("rows", []))
    recommended = int(core._number(model.get("recommended_rent")))
    used_count = int(core._number(model.get("used_comp_count")))
    verified = int(core._number(model.get("verified_comp_count")))
    requires_review = bool(model.get("requires_human_verification"))
    confidence = core._clean_text(model.get("confidence")) or "Weak rural fallback comps"

    if recommended > 0:
        state["rent"] = recommended
        state["rent_estimate"] = recommended
    state["rent_source"] = model.get("source", "RentCast rural rental intelligence")
    state["rent_confidence"] = confidence
    state["rent_verification_needed"] = "Yes" if requires_review or verified < 3 else "No"
    state["rent_requires_human_verification"] = requires_review
    state["rent_verification_reasons"] = list(model.get("verification_reasons", []) or [])
    state["verified_rent_comp_count"] = verified
    state["rent_comps"] = rows
    state["rentcast_rent_comps"] = rows
    state["rent_comp_count"] = used_count
    state["rentcast_comp_count"] = used_count
    state["rentcast_rent_comp_count"] = used_count
    state["rentcast_total_listing_count"] = int(model.get("total_listing_count", len(rows)) or 0)
    state["rent_comp_average"] = int(core._number(model.get("comp_average")))
    state["rentcast_rent_comp_average"] = int(core._number(model.get("comp_average")))
    state["rent_comp_median"] = int(core._number(model.get("comp_median")))
    state["rentcast_rent_comp_median"] = int(core._number(model.get("comp_median")))
    state["rental_demand_confidence"] = (
        "Strong rent comps" if confidence.startswith("Strong") and not requires_review
        else "Some rent comps" if confidence.startswith("Medium") and not requires_review
        else "Weak rent comps"
    )


def _table_rows(model: dict[str, Any], money: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in model.get("rows", []) or []:
        rows.append(
            {
                "Address": item.get("address", ""),
                "Beds": item.get("beds", 0),
                "Baths": item.get("baths", 0),
                "Sqft": item.get("sqft", 0),
                "Asking Rent": money(item.get("rent", 0)),
                "Distance": round(core._number(item.get("distance")), 2),
                "Status": item.get("status", ""),
                "Listed": item.get("listed_date", ""),
                "Last Seen": item.get("last_seen_date", ""),
                "Days Old": int(core._number(item.get("days_old"))),
                "Score": item.get("score", ""),
                "Used?": "Yes" if item.get("include_default") else "No",
                "Source": item.get("source", "RentCast Rental Listing"),
                "Why excluded / flags": "; ".join(item.get("flags", []) or []),
            }
        )
    return rows


def _render_rural_rent_intelligence(st: Any, ui: Any, data: dict[str, Any]) -> None:
    model = build_rent_display_model(st, data)
    _store_intelligent_rent_state(st, model)

    st.subheader("Rent Verification")
    st.caption(
        "Adaptive RentCast rental intelligence separates total listings from the quality comps "
        "used in the rent calculation. Advertised rents are evidence, not proof of executed leases."
    )

    total = int(model.get("total_listing_count", 0) or 0)
    verified = int(model.get("verified_comp_count", 0) or 0)
    recommended = int(core._number(model.get("recommended_rent")))
    if model.get("requires_human_verification"):
        st.warning(
            f"RentCast estimates {ui.money(recommended)}/month. {total} rental listing(s) were returned, "
            f"but only {verified} met the current quality-verification rules. Human review remains required."
        )
    else:
        st.success(
            f"RentCast supports {ui.money(recommended)}/month with {verified} quality-verified rental comp(s)."
        )

    if model.get("submitted_address"):
        st.caption(f"Address submitted to RentCast: {model['submitted_address']}")

    search = st.columns(4)
    search[0].metric("Search Mode", model.get("search_mode", "Adaptive"))
    search[1].metric(
        "Farthest Used Comp",
        f"{core._number(model.get('search_radius')):.1f} mi"
        if core._number(model.get("search_radius")) > 0
        else "Unavailable",
    )
    search[2].metric(
        "Oldest Used Listing",
        f"{int(model.get('search_days', 0) or 0):,} days"
        if int(model.get("search_days", 0) or 0) > 0
        else "Unavailable",
    )
    search[3].metric("Evidence", "Advertised asking rents")

    rows = _table_rows(model, ui.money)
    if rows:
        st.dataframe(ui.pd.DataFrame(rows), use_container_width=True)
    else:
        st.info("No rental-listing rows are available in this session.")

    primary = st.columns(4)
    primary[0].metric("Recommended Rent", ui.money(model.get("recommended_rent", 0)))
    primary[1].metric("RentCast AVM", ui.money(model.get("rentcast_avm", 0)))
    primary[2].metric(
        "Verified / Total",
        f"{verified} / {total}",
    )
    primary[3].metric("Used in Calculation", int(model.get("used_comp_count", 0) or 0))

    support = st.columns(4)
    support[0].metric("Quality Comp Average", ui.money(model.get("comp_average", 0)))
    support[1].metric("Quality Comp Median", ui.money(model.get("comp_median", 0)))
    support[2].metric(
        "Supported Range",
        f"{ui.money(model.get('rent_low', 0))} - {ui.money(model.get('rent_high', 0))}",
    )
    support[3].metric("Rent Confidence", model.get("confidence", "Missing"))

    quality = model.get("quality_summary", {}) or {}
    if quality:
        st.caption(
            "Quality breakdown: "
            f"{int(quality.get('strong', 0) or 0)} strong, "
            f"{int(quality.get('good', 0) or 0)} good, "
            f"{int(quality.get('weak', 0) or 0)} weak, "
            f"{int(quality.get('excluded', 0) or 0)} excluded."
        )
        disagreement = core._number(quality.get("avm_comp_disagreement_pct"))
        if disagreement > 0:
            st.caption(f"RentCast AVM versus quality-comp median difference: {disagreement:.1f}%.")

    for reason in model.get("verification_reasons", []) or []:
        st.warning(str(reason))
    st.info(
        "Rental records are advertised asking rents. Confirm at least three nearby current listings "
        "or obtain a local property-manager opinion before increasing the underwritten rent."
    )


def render_rent_fallback_section(st: Any, ui: Any) -> None:
    data = _intelligence_data(st)
    if _rural_preview_active(st, data):
        _render_rural_rent_intelligence(st, ui, data)
        return
    _ORIGINAL_RENDER(st, ui)


def install() -> bool:
    if getattr(rent_fallback_ui, "_rural_rent_ui_fix_installed", False):
        return True

    rent_scoring._rural_rent_ui_original_score = _ORIGINAL_SCORE
    rent_scoring._score_rent_comp = score_rent_comp_ui_hardened
    rent_fallback_ui._rural_rent_ui_original_render = _ORIGINAL_RENDER
    rent_fallback_ui.render_rent_fallback_section = render_rent_fallback_section
    rent_fallback_ui._rural_rent_ui_fix_installed = True
    return True


install()

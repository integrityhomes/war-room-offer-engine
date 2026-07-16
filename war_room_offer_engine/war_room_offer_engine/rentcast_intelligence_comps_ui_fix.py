from __future__ import annotations

from typing import Any

try:
    import rentcast_intelligence_core as core
    import rentcast_intelligence_preview as preview
    import rentcast_intelligence_quality_hardening as quality
    import rentcast_recorded_sales as sales
    import rentcast_recorded_sales_scoring as sale_scoring
    from ui_sections import comps_ui
except ImportError:
    try:
        from . import rentcast_intelligence_core as core
        from . import rentcast_intelligence_preview as preview
        from . import rentcast_intelligence_quality_hardening as quality
        from . import rentcast_recorded_sales as sales
        from . import rentcast_recorded_sales_scoring as sale_scoring
        from .ui_sections import comps_ui
    except ImportError:
        from war_room_offer_engine import rentcast_intelligence_core as core
        from war_room_offer_engine import rentcast_intelligence_preview as preview
        from war_room_offer_engine import rentcast_intelligence_quality_hardening as quality
        from war_room_offer_engine import rentcast_recorded_sales as sales
        from war_room_offer_engine import rentcast_recorded_sales_scoring as sale_scoring
        from war_room_offer_engine.ui_sections import comps_ui


_RECORDED_DATA_TYPE = "RentCast public-record closed sales"
_ORIGINAL_RENDER = getattr(
    comps_ui,
    "_recorded_sale_ui_original_render",
    comps_ui.render_automatic_sold_comps_section,
)
_ORIGINAL_SCORE = getattr(
    sale_scoring,
    "_recorded_sale_ui_original_score",
    sale_scoring._score_recorded_sale,
)


def _recorded_rows(state: Any) -> list[dict[str, Any]]:
    rows = state.get("auto_sold_comps", []) if hasattr(state, "get") else []
    return [dict(row) for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _recorded_preview_active(st: Any) -> bool:
    if not preview.preview_enabled(st):
        return False
    summary = st.session_state.get("auto_arv_summary", {}) or {}
    if isinstance(summary, dict) and summary.get("comp_data_type") == _RECORDED_DATA_TYPE:
        return True
    return any(
        row.get("record_type") == "recorded_sale"
        or str(row.get("source", "")).startswith("RentCast Recorded Sale")
        for row in _recorded_rows(st.session_state)
    )


def score_recorded_sale_ui_hardened(
    comp: dict[str, Any],
    subject: dict[str, Any],
    stage: dict[str, Any],
) -> dict[str, Any]:
    """Prevent materially different rural records from being labeled Strong."""
    row = dict(_ORIGINAL_SCORE(comp, subject, stage) or {})
    if row.get("score") == "Bad Comp":
        return row

    flags = list(row.get("flags", []) or [])
    sqft_delta = row.get("sqft_delta_pct")
    if sqft_delta is not None and core._number(sqft_delta) > 25:
        flags.append("square footage differs materially")

    material = any(
        flag in {
            "square footage differs materially",
            "bedroom count differs materially",
            "bathroom count differs materially",
            "year built differs materially",
            "acreage differs materially",
        }
        for flag in flags
    )
    if material:
        points = min(int(row.get("score_points", 0) or 0), 87)
        row.update(
            {
                "flags": sorted(set(flags)),
                "score_points": points,
                "score": sale_scoring._score_label(points, False),
            }
        )
    else:
        row["flags"] = sorted(set(flags))
    return row


def _subject_from_state(st: Any) -> dict[str, Any]:
    state = st.session_state
    return {
        "address": state.get("address", ""),
        "city": state.get("city", ""),
        "state": state.get("state", ""),
        "zip": state.get("zip", ""),
        "county": state.get("county", ""),
        "latitude": state.get("latitude"),
        "longitude": state.get("longitude"),
        "property_type": state.get("property_type", ""),
        "beds": state.get("beds", 0),
        "baths": state.get("baths", 0),
        "sqft": state.get("sqft", 0),
        "lot_size": state.get("lot_size", 0),
        "year_built": state.get("year_built", 0),
        "subdivision": state.get("subdivision", ""),
    }


def _stage_from_summary(st: Any, summary: dict[str, Any]) -> dict[str, Any]:
    radius = core._number(
        summary.get("search_radius")
        or st.session_state.get("arv_search_radius")
        or st.session_state.get("auto_comp_radius")
        or 50
    )
    days = int(
        core._number(
            summary.get("search_days")
            or st.session_state.get("arv_search_days")
            or 2555
        )
        or 2555
    )
    return {
        "name": (
            core._clean_text(summary.get("search_mode"))
            or core._clean_text(st.session_state.get("arv_search_mode"))
            or "Adaptive recorded sales"
        ),
        "radius": radius or 50.0,
        "days": days,
        "sqft_tolerance": 0.65,
    }


def _selection_summary(
    st: Any,
    scored_comps: list[dict[str, Any]],
    included_indexes: set[int],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    base = st.session_state.get("auto_arv_summary", {}) or {}
    base = dict(base) if isinstance(base, dict) else {}
    selected_rows: list[dict[str, Any]] = []
    for index, raw in enumerate(scored_comps):
        row = dict(raw)
        engine_eligible = bool(
            raw.get("engine_include_default", raw.get("include_default"))
        )
        row["engine_include_default"] = engine_eligible
        # Operators may remove an engine-selected comp, but cannot promote a row
        # that the recorded-sale quality engine rejected or left outside its top five.
        row["include_default"] = engine_eligible and index in included_indexes
        selected_rows.append(row)

    display, summary = quality.summarize_recorded_sales_quality(
        selected_rows,
        _subject_from_state(st),
        _stage_from_summary(st, base),
        int(base.get("candidate_comp_count", 0) or len(scored_comps)),
    )
    for key in (
        "search_trail",
        "subject_comp_removed_count",
        "candidate_comp_count",
        "comp_data_type",
        "sale_dates_unverified",
    ):
        if key in base and key not in summary:
            summary[key] = base.get(key)
    summary["manual_selection_active"] = True
    return display, summary


def _store_extended_summary(
    st: Any,
    ui: Any,
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    ui.store_auto_arv_summary(rows, summary)
    state = st.session_state
    state["auto_sold_comps"] = rows
    state["verified_sold_comp_count"] = int(summary.get("verified_sold_comp_count", 0) or 0)
    state["arv_requires_human_verification"] = bool(
        summary.get("arv_requires_human_verification", True)
    )
    state["arv_verification_reasons"] = list(summary.get("verification_reasons", []) or [])
    state["arv_search_mode"] = summary.get("search_mode", "")
    state["arv_search_radius"] = summary.get("search_radius", "")
    state["arv_search_days"] = int(summary.get("search_days", 0) or 0)
    state["arv_price_median"] = core._number(summary.get("price_median"))
    state["arv_median_ppsf"] = core._number(summary.get("median_price_per_sqft"))
    state["arv_ppsf_estimate"] = core._number(summary.get("ppsf_arv"))
    state["arv_method_disagreement_pct"] = core._number(
        summary.get("method_disagreement_pct")
    )


def _clear_recorded_state(st: Any, ui: Any) -> None:
    for key in (
        "auto_sold_comps",
        "auto_arv_summary",
        "auto_comp_summary_json",
        "excluded_comp_flags_json",
        "verified_sold_comp_count",
        "arv_verification_reasons",
        "arv_search_mode",
        "arv_search_radius",
        "arv_search_days",
        "arv_price_median",
        "arv_median_ppsf",
        "arv_ppsf_estimate",
        "arv_method_disagreement_pct",
    ):
        st.session_state.pop(key, None)
    st.session_state["arv_requires_human_verification"] = True
    st.session_state["use_auto_arv_over_manual_comps"] = False
    ui.store_auto_arv_summary([], ui.calculate_arv_from_comps([]))


def _render_recorded_sale_intelligence(st: Any, ui: Any) -> None:
    pd = ui.pd
    money = ui.money
    safe_float = ui.safe_float

    scored_comps = _recorded_rows(st.session_state)
    base_summary = st.session_state.get("auto_arv_summary", {}) or {}
    base_summary = dict(base_summary) if isinstance(base_summary, dict) else {}

    st.markdown("### Recorded Sale Intelligence")
    st.caption(
        "This preview uses adaptive RentCast public-record sales. Listing prices are "
        "not treated as closed sales, and the legacy radius/date controls are hidden "
        "because they do not describe the automatic rural search."
    )

    top = st.columns(4)
    top[0].metric("Search Mode", base_summary.get("search_mode") or st.session_state.get("arv_search_mode") or "Adaptive")
    top[1].metric("Radius Used", base_summary.get("search_radius") or st.session_state.get("arv_search_radius") or "Unavailable")
    search_days = int(
        base_summary.get("search_days")
        or st.session_state.get("arv_search_days")
        or 0
    )
    top[2].metric("Lookback", f"{search_days:,} days" if search_days else "Unavailable")
    top[3].metric("Source", "Recorded public sales")

    st.info(
        "To refresh these records, return to One-Load and run Pull Everything & Tell Me. "
        "The manual comp entry section below remains available for local knowledge."
    )

    use_col, clear_col = st.columns(2)
    with use_col:
        use_best_clicked = st.button(
            "Use Recorded-Sale ARV",
            key="use_best_auto_arv",
        )
    with clear_col:
        clear_clicked = st.button(
            "Clear Auto Comps",
            key="clear_auto_sold_comps",
        )

    if clear_clicked:
        _clear_recorded_state(st, ui)
        st.success("Recorded-sale comps cleared.")
        return

    if not scored_comps:
        st.warning("No recorded-sale comps are loaded in this session.")
        return

    st.write("Recorded Sale Preview")
    included_indexes: set[int] = set()
    for index, comp in enumerate(scored_comps):
        eligible = bool(
            comp.get("engine_include_default", comp.get("include_default"))
        )
        widget_key = f"auto_comp_include_{index}"
        if not eligible:
            st.session_state[widget_key] = False
        include = st.checkbox(
            f"Use comp {index + 1}: {comp.get('comp_address') or 'Unknown address'}",
            value=eligible,
            key=widget_key,
            disabled=not eligible,
            help=(
                "You may remove an engine-selected comp. Rejected or lower-ranked rows "
                "remain locked so weak evidence cannot be promoted into the ARV."
            ),
        )
        if include and eligible:
            included_indexes.add(index)

    display_rows, summary = _selection_summary(st, scored_comps, included_indexes)
    _store_extended_summary(st, ui, display_rows, summary)

    table_rows = []
    for comp in display_rows:
        table_rows.append(
            {
                "Address": comp.get("comp_address", ""),
                "Sold Price": money(comp.get("sold_price", 0)),
                "Sold Date": comp.get("sold_date", ""),
                "Beds": comp.get("beds", 0),
                "Baths": comp.get("baths", 0),
                "Sqft": comp.get("square_feet", 0),
                "Distance": comp.get("distance_miles", 0),
                "$/Sqft": (
                    f"${core._number(comp.get('price_per_sqft')):,.2f}"
                    if core._number(comp.get("price_per_sqft")) > 0
                    else ""
                ),
                "Source": comp.get("source", ""),
                "Score": comp.get("score", ""),
                "Include?": "Yes" if comp.get("include_default") else "No",
                "Why excluded / flags": "; ".join(comp.get("flags", []) or []),
            }
        )
    st.dataframe(pd.DataFrame(table_rows), use_container_width=True)

    metrics = st.columns(4)
    metrics[0].metric("Recommended ARV", money(summary.get("recommended_arv", 0)))
    metrics[1].metric(
        "ARV Range",
        f"{money(summary.get('low_arv', 0))} - {money(summary.get('high_arv', 0))}",
    )
    metrics[2].metric("ARV Confidence", summary.get("arv_confidence", "Not enough data"))
    metrics[3].metric(
        "Verified / Total",
        f"{int(summary.get('verified_sold_comp_count', 0) or 0)} / {len(scored_comps)}",
    )

    methods = st.columns(4)
    methods[0].metric("Median Sale Price", money(summary.get("price_median", 0)))
    methods[1].metric(
        "Median $/Sqft",
        f"${core._number(summary.get('median_price_per_sqft')):,.2f}",
    )
    methods[2].metric("Sqft-Based ARV", money(summary.get("ppsf_arv", 0)))
    methods[3].metric(
        "Method Difference",
        f"{core._number(summary.get('method_disagreement_pct')):.1f}%",
    )

    st.info(summary.get("explanation", ""))
    for reason in summary.get("verification_reasons", []) or []:
        st.warning(str(reason))
    if summary.get("condition_evidence") == "Unverified":
        st.warning(
            "This is recorded-sale support, not proof of renovated condition. "
            "Verify comp photos, MLS remarks, and the subject's repair level before "
            "using it as a final wholesale ARV."
        )

    if use_best_clicked:
        if safe_float(summary.get("recommended_arv", 0)) > 0:
            st.session_state["use_auto_arv_over_manual_comps"] = True
            st.success(
                "Recorded-sale ARV selected. Human-verification warnings remain active, "
                "and a manual ARV override still has highest priority."
            )
        else:
            st.warning("No recorded-sale ARV is available yet.")


def render_automatic_sold_comps_section(st: Any, ui: Any) -> None:
    if _recorded_preview_active(st):
        _render_recorded_sale_intelligence(st, ui)
        return
    _ORIGINAL_RENDER(st, ui)


def install() -> bool:
    if getattr(comps_ui, "_recorded_sale_ui_fix_installed", False):
        return True

    sale_scoring._recorded_sale_ui_original_score = _ORIGINAL_SCORE
    sale_scoring._score_recorded_sale = score_recorded_sale_ui_hardened
    sales._score_recorded_sale = score_recorded_sale_ui_hardened

    comps_ui._recorded_sale_ui_original_render = _ORIGINAL_RENDER
    comps_ui.render_automatic_sold_comps_section = render_automatic_sold_comps_section
    comps_ui._recorded_sale_ui_fix_installed = True
    return True


install()

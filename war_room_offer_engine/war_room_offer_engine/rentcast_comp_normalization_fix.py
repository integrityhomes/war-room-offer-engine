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

_ORIGINAL_ENRICH = getattr(rentcast, "_rentcast_comp_normalization_original_enrich", rentcast.enrich_property_with_rentcast)
_ORIGINAL_BRIDGE_HYDRATE = getattr(bridge, "_rentcast_comp_normalization_original_hydrate", bridge._hydrate_state)
_ORIGINAL_BOOTSTRAP_HYDRATE = getattr(bootstrap, "_rentcast_comp_normalization_original_hydrate", bootstrap.hydrate_rentcast_state)
_UNVERIFIED_ARV_SOURCE = "RentCast Value Comps — dates unverified"
_SUFFIX_ALIASES = {
    "street": "st", "st": "st", "road": "rd", "rd": "rd", "drive": "dr", "dr": "dr",
    "avenue": "ave", "ave": "ave", "lane": "ln", "ln": "ln", "court": "ct", "ct": "ct",
    "boulevard": "blvd", "blvd": "blvd", "place": "pl", "pl": "pl", "parkway": "pkwy",
    "pkwy": "pkwy", "highway": "hwy", "hwy": "hwy", "trail": "trl", "trl": "trl",
    "terrace": "ter", "ter": "ter", "circle": "cir", "cir": "cir", "way": "way",
}
_DIRECTION_ALIASES = {
    "north": "n", "n": "n", "south": "s", "s": "s", "east": "e", "e": "e", "west": "w", "w": "w",
    "northeast": "ne", "ne": "ne", "northwest": "nw", "nw": "nw",
    "southeast": "se", "se": "se", "southwest": "sw", "sw": "sw",
}
_UNIT_MARKERS = {"apt", "apartment", "unit", "suite", "ste"}
_RESET_STATE_KEYS = set("""
rentcast_rent_comps rent_comps rentcast_comp_count rentcast_rent_comp_count rent_comp_count
rent_comp_average rentcast_rent_comp_average rent_comp_median rentcast_rent_comp_median
rentcast_sold_comps rentcast_sold_comp_count rentcast_value_comp_count auto_sold_comps auto_comp_count
auto_comp_source auto_arv_summary auto_recommended_arv auto_low_arv auto_conservative_arv
auto_average_arv auto_high_arv strong_comp_count good_comp_count weak_comp_count excluded_comp_count
auto_comp_messages auto_comp_summary_json excluded_comp_flags_json rentcast_arv arv arv_source_used
value_source arv_confidence arv_fallback_reason
""".split())


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _clean_tokens(value: Any) -> list[str]:
    return re.findall(r"[a-z0-9]+", str(value or "").lower().replace("#", " unit "))


def _canonical_street_tokens(tokens: list[str]) -> list[str]:
    return [_DIRECTION_ALIASES.get(token, _SUFFIX_ALIASES.get(token, token)) for token in tokens]


def _split_street_and_unit(street_line: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    tokens = _clean_tokens(street_line)
    unit_index = next((i for i, token in enumerate(tokens) if token in _UNIT_MARKERS), None)
    street_tokens = tokens if unit_index is None else tokens[:unit_index]
    unit_tokens = [] if unit_index is None else tokens[unit_index + 1 :]
    return tuple(_canonical_street_tokens(street_tokens)), tuple(unit_tokens)


def _address_identity(value: Any) -> dict[str, Any]:
    parts = [part.strip() for part in str(value or "").split(",") if part.strip()]
    if not parts:
        return {"street": (), "unit": (), "city": "", "state": "", "zip": ""}
    street, unit = _split_street_and_unit(parts[0])
    city = state = zipcode = ""
    if len(parts) >= 3:
        city = " ".join(_clean_tokens(parts[1]))
        region = _clean_tokens(" ".join(parts[2:]))
        state = next((token for token in region if len(token) == 2 and token.isalpha()), "")
        zipcode = next((token[:5] for token in region if token.isdigit() and len(token) >= 5), "")
    elif len(parts) == 2:
        region = _clean_tokens(parts[1])
        zipcode = next((token[:5] for token in reversed(region) if token.isdigit() and len(token) >= 5), "")
        state_index = next((i for i in range(len(region) - 1, -1, -1) if len(region[i]) == 2 and region[i].isalpha()), None)
        if state_index is None:
            city_tokens = [token for token in region if token != zipcode]
        else:
            state, city_tokens = region[state_index], region[:state_index]
        city = " ".join(city_tokens)
    return {"street": street, "unit": unit, "city": city, "state": state, "zip": zipcode}


def _street_key(value: Any) -> str:
    identity = _address_identity(value)
    key = " ".join(identity["street"])
    return f"{key} unit {' '.join(identity['unit'])}".strip() if identity["unit"] else key


def _is_subject_comp(subject_address: str, comp_address: str) -> bool:
    subject, comp = _address_identity(subject_address), _address_identity(comp_address)
    if not subject["street"] or subject["street"] != comp["street"]:
        return False
    if subject["unit"] or comp["unit"]:
        if not subject["unit"] or not comp["unit"] or subject["unit"] != comp["unit"]:
            return False
    return not any(subject[key] and comp[key] and subject[key] != comp[key] for key in ["city", "state", "zip"])


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
        "missing sold price", "missing sold date", "missing sqft", "too far away",
        "sqft more than 25% different", "different property type", "possible distressed sale",
    }
    return any(flag in excluded for flag in flags)


def _score_rentcast_stage(
    comps: list[dict[str, Any]], subject: dict[str, Any], radius_label: str, date_range_label: str
) -> list[dict[str, Any]]:
    radius, scored = sold.radius_to_float(radius_label), []
    for comp in comps:
        row = sold.score_sold_comp(comp, subject, radius, date_range_label)
        flags, points = list(row.get("flags", []) or []), int(row.get("score_points", 0) or 0)
        source = str(comp.get("source", "") or "").strip().lower()
        if "missing sold date" in flags and source.startswith("rentcast"):
            flags.remove("missing sold date")
            flags.append("sale date unavailable from RentCast; verify before relying on ARV")
            points = min(points + 15, 100)
        score = _score_label(points, flags)
        scored.append({**row, "flags": sorted(set(flags)), "score_points": max(min(points, 100), 0),
                       "score": score, "include_default": score != "Bad Comp" and not _critical_exclusion(flags)})

    eligible = [_number(row.get("sold_price")) for row in scored if row.get("include_default") and _number(row.get("sold_price")) > 0]
    center = median(eligible) if len(eligible) >= 3 else 0
    if center > 0:
        updated = []
        for row in scored:
            flags, points = list(row.get("flags", []) or []), int(row.get("score_points", 0) or 0)
            price, include = _number(row.get("sold_price")), bool(row.get("include_default"))
            if include and (price < center * 0.60 or price > center * 1.60):
                flags.append("price outlier versus comparable local properties")
                points, include = points - 25, False
            score = _score_label(points, flags)
            updated.append({**row, "flags": sorted(set(flags)), "score_points": max(points, 0),
                            "score": score, "include_default": include and score != "Bad Comp"})
        scored = updated
    return scored


def build_sold_comp_intelligence_fixed(
    data: dict[str, Any], sold_comps: list[dict[str, Any]], full_address: str = ""
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    subject_address = full_address or rentcast.build_full_address(data)
    filtered, removed = [], 0
    for comp in sold_comps or []:
        if not isinstance(comp, dict) or _number(comp.get("sold_price")) <= 0:
            continue
        if _is_subject_comp(subject_address, str(comp.get("comp_address", "") or "")):
            removed += 1
        else:
            filtered.append(comp)

    subject, candidates = rentcast._comp_subject(data, subject_address), []
    for stage_index, (radius, date_range) in enumerate(rentcast.AUTO_COMP_SEARCH_STAGES):
        scored = _score_rentcast_stage(filtered, subject, radius, date_range)
        summary = sold.calculate_arv_from_comps(scored)
        included = [row for row in scored if row.get("include_default") and row.get("score") != "Bad Comp"]
        quality = sum(row.get("score") in ["Strong Comp", "Good Comp"] for row in included)
        rank = (int(len(included) >= 3 and _number(summary.get("recommended_arv")) > 0), quality, len(included),
                int(_number(summary.get("recommended_arv")) > 0), -stage_index)
        candidates.append((scored, summary, radius, date_range, rank))
        if rank[0]:
            break
    if candidates:
        scored, summary, radius, date_range, _ = max(candidates, key=lambda item: item[4])
    else:
        scored, summary, radius, date_range = [], sold.calculate_arv_from_comps([]), "1 mile", "Last 12 months"

    included = [row for row in scored if row.get("include_default") and row.get("score") != "Bad Comp"]
    unverified = any("sale date unavailable from RentCast" in " ".join(map(str, row.get("flags", []))) for row in included)
    summary = {**summary, "search_radius": radius, "date_range": date_range,
               "subject_comp_removed_count": removed, "candidate_comp_count": len(filtered),
               "included_comp_count": len(included), "sale_dates_unverified": unverified,
               "comp_data_type": "RentCast value comparables"}
    if summary.get("recommended_arv", 0) and unverified:
        summary["arv_confidence"] = "Weak"
        summary["explanation"] = (
            f"Provisional ARV uses {len(included)} nearby RentCast value comparable(s). "
            "RentCast did not provide sale dates, so verify recent closed sales before relying on this ARV."
        )
    return scored, summary


def _round_half_up(value: float) -> int:
    return int(float(value) + 0.5) if value > 0 else 0


def _rent_values(comps: Any) -> list[float]:
    return [_number(row.get("rent")) for row in comps if isinstance(row, dict) and _number(row.get("rent")) > 0] if isinstance(comps, list) else []


def _rent_statistics(comps: Any) -> tuple[int, int]:
    rents = _rent_values(comps)
    return (_round_half_up(sum(rents) / len(rents)), _round_half_up(float(median(rents)))) if rents else (0, 0)


def _apply_result_rent_stats(result: dict[str, Any]) -> None:
    for key in ["rent_comps", "rentcast_rent_comps"]:
        if key in result:
            average, med = _rent_statistics(result.get(key))
            result.update({"rent_comp_average": average, "rentcast_rent_comp_average": average,
                           "rent_comp_median": med, "rentcast_rent_comp_median": med})
            return


def enrich_property_with_rentcast_fixed(data: dict[str, Any], api_key: str, session=None) -> dict[str, Any]:
    enriched = _ORIGINAL_ENRICH(data, api_key, **({} if session is None else {"session": session}))
    _apply_result_rent_stats(enriched)
    summary = enriched.get("auto_arv_summary", {}) or {}
    if summary.get("sale_dates_unverified") and _number(summary.get("recommended_arv")) > 0:
        enriched.update({"arv": _number(summary.get("recommended_arv")), "arv_source": _UNVERIFIED_ARV_SOURCE,
                         "arv_confidence": "Weak"})
    return enriched


def _store_rent_stats(st, result: dict[str, Any] | None = None) -> None:
    result, comps_present, comps = result or {}, False, []
    for key in ["rent_comps", "rentcast_rent_comps"]:
        if key in result:
            comps_present, comps = True, result.get(key)
            break
    if comps_present:
        comps = comps if isinstance(comps, list) else []
        average, med = _rent_statistics(comps)
        st.session_state.update({"rentcast_rent_comps": comps, "rent_comps": comps,
                                 "rentcast_comp_count": len(comps), "rentcast_rent_comp_count": len(comps),
                                 "rent_comp_count": len(comps)})
    else:
        state_comps = st.session_state.get("rentcast_rent_comps") or st.session_state.get("rent_comps") or []
        if _rent_values(state_comps):
            average, med = _rent_statistics(state_comps)
        else:
            average = int(_number(result.get("rent_comp_average")) or _number(st.session_state.get("rent_comp_average")))
            med = int(_number(result.get("rent_comp_median")) or _number(st.session_state.get("rent_comp_median")))
    st.session_state.update({"rent_comp_average": average, "rentcast_rent_comp_average": average,
                             "rent_comp_median": med, "rentcast_rent_comp_median": med})


def _clear_stale_unverified_source(st, result: dict[str, Any]) -> None:
    sources = {str(st.session_state.get("arv_source_used", "") or ""), str(st.session_state.get("value_source", "") or "")}
    if _UNVERIFIED_ARV_SOURCE not in sources:
        return
    auto_arv, rentcast_arv = _number(result.get("auto_recommended_arv")), _number(result.get("rentcast_arv"))
    current_arv = _number(result.get("arv")) or auto_arv or rentcast_arv
    source = str(result.get("arv_source") or result.get("value_source") or "").strip()
    source = source or ("Automatic Sold Comps" if auto_arv > 0 else "RentCast AVM only" if rentcast_arv > 0 else "")
    if current_arv > 0 and source and source != _UNVERIFIED_ARV_SOURCE:
        st.session_state.update({"arv": int(current_arv), "arv_source_used": source, "value_source": source,
                                 "arv_confidence": str(result.get("arv_confidence") or "Weak"),
                                 "arv_fallback_reason": str(result.get("arv_fallback_reason") or "")})
    elif current_arv <= 0:
        st.session_state.update({"arv": 0, "arv_source_used": "", "value_source": "",
                                 "arv_confidence": "Not enough data",
                                 "arv_fallback_reason": "No current-property ARV source is available."})


def _synchronize_current_auto_state(st, result: dict[str, Any], summary: dict[str, Any]) -> None:
    state = st.session_state
    state["auto_arv_summary"] = summary
    scored = result.get("auto_sold_comps") if "auto_sold_comps" in result else ([] if not summary else state.get("auto_sold_comps") or [])
    scored = scored if isinstance(scored, list) else []
    state.update({"auto_sold_comps": scored, "auto_comp_count": len(scored), "auto_comp_source": "RentCast" if scored else ""})
    if "rentcast_sold_comps" in result or not summary:
        raw = result.get("rentcast_sold_comps", []) if summary or "rentcast_sold_comps" in result else []
        raw = raw if isinstance(raw, list) else []
        state.update({"rentcast_sold_comps": raw, "rentcast_sold_comp_count": len(raw), "rentcast_value_comp_count": len(raw)})
    auto_arv = _number(result.get("auto_recommended_arv")) or _number(summary.get("recommended_arv"))
    state["auto_recommended_arv"] = int(auto_arv) if auto_arv > 0 else 0
    for state_key, result_key, summary_key in [
        ("auto_low_arv", "auto_low_arv", "low_arv"), ("auto_conservative_arv", "auto_conservative_arv", "conservative_arv"),
        ("auto_average_arv", "auto_average_arv", "average_arv"), ("auto_high_arv", "auto_high_arv", "high_arv"),
    ]:
        value = _number(result.get(result_key)) or _number(summary.get(summary_key))
        state[state_key] = int(value) if value > 0 else 0
    for key in ["strong_comp_count", "good_comp_count", "weak_comp_count", "excluded_comp_count"]:
        state[key] = int(summary.get(key, 0) or 0)
    if not summary:
        state.update({"auto_comp_messages": [], "auto_comp_summary_json": "[]", "excluded_comp_flags_json": "[]"})


def _store_unverified_source(st, result: dict[str, Any] | None = None) -> None:
    result, summary_present = result or {}, "auto_arv_summary" in (result or {})
    if summary_present:
        candidate = result.get("auto_arv_summary")
        summary = candidate if isinstance(candidate, dict) else {}
        _synchronize_current_auto_state(st, result, summary)
    else:
        candidate = st.session_state.get("auto_arv_summary")
        summary = candidate if isinstance(candidate, dict) else {}
    if summary.get("sale_dates_unverified") and _number(summary.get("recommended_arv")) > 0:
        st.session_state.update({"arv": int(_number(summary.get("recommended_arv"))),
                                 "arv_source_used": _UNVERIFIED_ARV_SOURCE, "value_source": _UNVERIFIED_ARV_SOURCE,
                                 "arv_confidence": "Weak", "arv_fallback_reason": summary.get("explanation", "RentCast comp dates require verification.")})
    elif summary_present:
        _clear_stale_unverified_source(st, result)


def bridge_hydrate_fixed(result: dict[str, Any]) -> None:
    _ORIGINAL_BRIDGE_HYDRATE(result)
    try:
        import streamlit as st
    except Exception:
        return
    _store_rent_stats(st, result)
    _store_unverified_source(st, result)


def _current_property_present(st) -> bool:
    return any(str(st.session_state.get(key, "") or "").strip() for key in ["decision_property_input", "one_load_property_address", "one_load_listing_url", "address"])


def _clear_property_rentcast_state(st) -> None:
    for key in _RESET_STATE_KEYS:
        st.session_state.pop(key, None)


def bootstrap_hydrate_fixed(st) -> None:
    _ORIGINAL_BOOTSTRAP_HYDRATE(st)
    normalized = st.session_state.get("one_load_normalized", {}) or {}
    data = normalized.get("data", {}) if isinstance(normalized, dict) else {}
    last_pull = st.session_state.get("last_auto_pull", {}) or {}
    source = data if isinstance(data, dict) and data else last_pull if isinstance(last_pull, dict) else {}
    if not source and not _current_property_present(st):
        _clear_property_rentcast_state(st)
        return
    _store_rent_stats(st, source)
    _store_unverified_source(st, source)


def install() -> bool:
    if not getattr(rentcast, "_rentcast_comp_normalization_fix_installed", False):
        rentcast._rentcast_comp_normalization_original_enrich = _ORIGINAL_ENRICH
        bridge._rentcast_comp_normalization_original_hydrate = _ORIGINAL_BRIDGE_HYDRATE
        bootstrap._rentcast_comp_normalization_original_hydrate = _ORIGINAL_BOOTSTRAP_HYDRATE
    rentcast.build_sold_comp_intelligence = build_sold_comp_intelligence_fixed
    rentcast.enrich_property_with_rentcast = enrich_property_with_rentcast_fixed
    bridge.enrich_property_with_rentcast = enrich_property_with_rentcast_fixed
    bridge._hydrate_state = bridge_hydrate_fixed
    bootstrap.build_sold_comp_intelligence = build_sold_comp_intelligence_fixed
    bootstrap.hydrate_rentcast_state = bootstrap_hydrate_fixed
    rentcast._rentcast_comp_normalization_fix_installed = True
    return True


install()

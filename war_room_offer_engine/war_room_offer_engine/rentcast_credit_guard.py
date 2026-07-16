from __future__ import annotations

import os
import re
import time
from typing import Any, Callable

try:
    import address_rentcast_bridge as bridge
    import deal_decision_ui as decision_ui
    import rentcast_auto_enrichment as rentcast
    import rentcast_intelligence_preview as preview
    import rentcast_property_records as records
except ImportError:
    try:
        from . import address_rentcast_bridge as bridge
        from . import deal_decision_ui as decision_ui
        from . import rentcast_auto_enrichment as rentcast
        from . import rentcast_intelligence_preview as preview
        from . import rentcast_property_records as records
    except ImportError:
        from war_room_offer_engine import address_rentcast_bridge as bridge
        from war_room_offer_engine import deal_decision_ui as decision_ui
        from war_room_offer_engine import rentcast_auto_enrichment as rentcast
        from war_room_offer_engine import rentcast_intelligence_preview as preview
        from war_room_offer_engine import rentcast_property_records as records


CACHE_TTL_SECONDS = int(getattr(records, "CACHE_TTL_SECONDS", 6 * 60 * 60) or 6 * 60 * 60)
CONFIRM_KEY = "rentcast_credit_guard_confirm_refresh"
LAST_PROPERTY_KEY = "rentcast_credit_guard_last_property"
LAST_PULL_EPOCH_KEY = "rentcast_credit_guard_last_pull_epoch"
LAST_STATS_KEY = "rentcast_credit_guard_last_run_stats"
LAST_CONFIRM_PROPERTY_KEY = "rentcast_credit_guard_confirmation_property"

_RUN_CONTEXT: dict[str, Any] = {
    "active": False,
    "limit": 0,
    "successful_requests": 0,
    "cache_hits": 0,
    "blocked_requests": 0,
    "request_log": [],
}

_ORIGINAL_REQUEST_JSON = getattr(
    records, "_rentcast_credit_guard_original_request_json", records._request_json
)
_ORIGINAL_RENTCAST_GET_JSON = getattr(
    rentcast, "_rentcast_credit_guard_original_get_json", rentcast._get_json
)
_ORIGINAL_PROPERTY_FACTS = getattr(
    bridge, "_rentcast_credit_guard_original_property_facts", bridge._property_facts
)
_ORIGINAL_DECISION_RENDER = getattr(
    decision_ui, "_rentcast_credit_guard_original_render", decision_ui.render
)


def _clean_property(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"https?://(?:www\.)?", "", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _is_url(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return text.startswith("http://") or text.startswith("https://") or "www." in text


def estimate_request_range(state: Any, preview_on: bool | None = None) -> tuple[int, int]:
    """Estimate successful RentCast requests for one uncached analysis.

    The range includes the normal subject/rent/value calls and any automatic
    address-only retry. Rural preview adds recorded-sale and rental-listing
    expansion. Saved Deal Library loads and fresh in-process cache hits can use
    zero new requests.
    """
    preview_on = preview.preview_enabled() if preview_on is None else bool(preview_on)
    value = state.get("decision_property_input", "") if hasattr(state, "get") else ""
    listing_url = _is_url(value)
    if preview_on:
        return (4, 8) if listing_url else (5, 9)
    return (2, 4) if listing_url else (3, 5)


def _configured_limit(default_maximum: int) -> int:
    raw = str(os.getenv("RENTCAST_MAX_REQUESTS_PER_PULL", "") or "").strip()
    try:
        configured = int(raw)
    except Exception:
        configured = 0
    return max(1, min(configured or int(default_maximum), int(default_maximum)))


def _current_property(state: Any) -> str:
    if not hasattr(state, "get"):
        return ""
    return _clean_property(
        state.get("decision_property_input")
        or state.get("one_load_property_address")
        or state.get("one_load_listing_url")
        or state.get("address")
    )


def duplicate_analysis_is_fresh(state: Any, now: float | None = None) -> bool:
    if not hasattr(state, "get"):
        return False
    current = _current_property(state)
    previous = _clean_property(state.get(LAST_PROPERTY_KEY, ""))
    try:
        pulled_at = float(state.get(LAST_PULL_EPOCH_KEY, 0) or 0)
    except Exception:
        pulled_at = 0
    now = time.time() if now is None else float(now)
    has_result = bool(state.get("one_load_normalized") or state.get("decision_result"))
    return bool(
        current
        and previous
        and current == previous
        and pulled_at > 0
        and now - pulled_at <= CACHE_TTL_SECONDS
        and has_result
    )


def _fresh_cached_request(endpoint: str, api_key: str, params: dict[str, Any], session: Any) -> bool:
    try:
        key = records._cache_key(endpoint, api_key, params, session)
        cached = records._RESPONSE_CACHE.get(key)
        return bool(cached and time.time() - float(cached[0]) <= CACHE_TTL_SECONDS)
    except Exception:
        return False


def _budget_blocked_result(params: dict[str, Any]) -> dict[str, Any]:
    _RUN_CONTEXT["blocked_requests"] = int(_RUN_CONTEXT.get("blocked_requests", 0) or 0) + 1
    return {
        "ok": False,
        "error": (
            "RentCast per-pull request budget reached. The app stopped before making another "
            "billable request. Use the available evidence or intentionally start a new pull with "
            "a larger configured budget."
        ),
        "submitted_params": dict(params or {}),
        "cache_hit": False,
        "request_budget_blocked": True,
    }


def request_json_budgeted(
    endpoint: str,
    api_key: str,
    params: dict[str, Any],
    session: Any = None,
) -> dict[str, Any]:
    """Count and cap successful preview-mode RentCast requests.

    PR #67 routes all preview-mode RentCast endpoints through this low-level
    helper. Fresh cache hits remain allowed even after the budget is reached.
    """
    if not _RUN_CONTEXT.get("active") or not preview.preview_enabled():
        return _ORIGINAL_REQUEST_JSON(endpoint, api_key, params, session=session)

    actual_session = session or getattr(rentcast, "requests", None)
    is_cached = _fresh_cached_request(endpoint, api_key, dict(params or {}), actual_session)
    successful = int(_RUN_CONTEXT.get("successful_requests", 0) or 0)
    limit = int(_RUN_CONTEXT.get("limit", 0) or 0)
    if not is_cached and limit > 0 and successful >= limit:
        return _budget_blocked_result(dict(params or {}))

    result = _ORIGINAL_REQUEST_JSON(endpoint, api_key, params, session=session)
    if result.get("ok"):
        if result.get("cache_hit"):
            _RUN_CONTEXT["cache_hits"] = int(_RUN_CONTEXT.get("cache_hits", 0) or 0) + 1
        else:
            _RUN_CONTEXT["successful_requests"] = successful + 1
            _RUN_CONTEXT.setdefault("request_log", []).append(
                {"endpoint": str(endpoint), "params": dict(params or {})}
            )
    return result


def rentcast_get_json_budgeted(
    endpoint: str,
    api_key: str,
    params: dict[str, Any],
    session: Any = None,
) -> dict[str, Any]:
    """Count and cap the current production AVM calls when preview is off."""
    if not _RUN_CONTEXT.get("active") or preview.preview_enabled():
        return _ORIGINAL_RENTCAST_GET_JSON(endpoint, api_key, params, session=session)

    successful = int(_RUN_CONTEXT.get("successful_requests", 0) or 0)
    limit = int(_RUN_CONTEXT.get("limit", 0) or 0)
    if limit > 0 and successful >= limit:
        return _budget_blocked_result(dict(params or {}))

    result = _ORIGINAL_RENTCAST_GET_JSON(endpoint, api_key, params, session=session)
    if result.get("ok"):
        _RUN_CONTEXT["successful_requests"] = successful + 1
        _RUN_CONTEXT.setdefault("request_log", []).append(
            {"endpoint": str(endpoint), "params": dict(params or {})}
        )
    return result


def property_facts_budgeted(address: str, api_key: str) -> tuple[dict[str, Any], str]:
    """Count the production subject-property lookup when preview is off."""
    if not _RUN_CONTEXT.get("active") or preview.preview_enabled():
        return _ORIGINAL_PROPERTY_FACTS(address, api_key)
    if not str(address or "").strip() or not str(api_key or "").strip():
        return _ORIGINAL_PROPERTY_FACTS(address, api_key)

    successful = int(_RUN_CONTEXT.get("successful_requests", 0) or 0)
    limit = int(_RUN_CONTEXT.get("limit", 0) or 0)
    if limit > 0 and successful >= limit:
        _RUN_CONTEXT["blocked_requests"] = int(_RUN_CONTEXT.get("blocked_requests", 0) or 0) + 1
        return {}, "RentCast per-pull request budget reached before the subject-property lookup."

    facts, error = _ORIGINAL_PROPERTY_FACTS(address, api_key)
    lowered = str(error or "").lower()
    not_billed = "request error" in lowered or "http " in lowered
    if not not_billed:
        _RUN_CONTEXT["successful_requests"] = successful + 1
        _RUN_CONTEXT.setdefault("request_log", []).append(
            {"endpoint": "RentCast /properties subject lookup", "params": {"address": address}}
        )
    return facts, error


def _reset_confirmation_for_property(st: Any) -> None:
    state = st.session_state
    current = _current_property(state)
    previous = _clean_property(state.get(LAST_CONFIRM_PROPERTY_KEY, ""))
    if current != previous:
        state[CONFIRM_KEY] = False
        state[LAST_CONFIRM_PROPERTY_KEY] = current
    if not state.get("deal_library_force_refresh", False):
        state[CONFIRM_KEY] = False


def render_credit_panel(st: Any) -> None:
    state = st.session_state
    _reset_confirmation_for_property(st)
    preview_on = preview.preview_enabled(st)
    minimum, maximum = estimate_request_range(state, preview_on=preview_on)
    limit = _configured_limit(maximum)
    state["rentcast_credit_guard_estimated_min"] = minimum
    state["rentcast_credit_guard_estimated_max"] = maximum
    state["rentcast_credit_guard_limit"] = limit

    mode = "Rural intelligence" if preview_on else "Standard RentCast"
    st.info(
        f"RentCast request budget — {mode}: an uncached fresh pull is estimated to use "
        f"{minimum}–{maximum} successful API request(s). Saved deals and fresh cache hits use 0 new requests. "
        f"This run is hard-capped at {limit}."
    )

    last = state.get(LAST_STATS_KEY, {}) or {}
    if isinstance(last, dict) and last:
        actual = int(last.get("successful_requests", 0) or 0)
        hits = int(last.get("cache_hits", 0) or 0)
        blocked = int(last.get("blocked_requests", 0) or 0)
        text = f"Last analysis: {actual} new RentCast request(s), {hits} cache hit(s)"
        if blocked:
            text += f", {blocked} request(s) blocked by the budget"
        st.caption(text + ".")

    if duplicate_analysis_is_fresh(state) and not state.get("deal_library_force_refresh", False):
        age_minutes = max(
            int((time.time() - float(state.get(LAST_PULL_EPOCH_KEY, 0) or 0)) / 60),
            0,
        )
        st.success(
            f"This property's current analysis is about {age_minutes} minute(s) old. Reuse it; changing "
            "price or deal lane does not require another paid pull."
        )

    if state.get("deal_library_force_refresh", False):
        st.warning(
            "Refresh live paid data bypasses the saved Deal Library result and may consume the full request budget."
        )
        st.checkbox(
            f"I understand this refresh may use up to {maximum} RentCast requests",
            key=CONFIRM_KEY,
        )


def _button_should_be_disabled(st: Any) -> tuple[bool, str]:
    state = st.session_state
    if state.get("deal_library_force_refresh", False) and not state.get(CONFIRM_KEY, False):
        return True, "Confirm the RentCast request cost above before forcing a fresh paid-data pull."
    if duplicate_analysis_is_fresh(state) and not state.get("deal_library_force_refresh", False):
        return True, (
            "A fresh analysis for this property is already loaded. Change the price or lane without repulling, "
            "or intentionally enable paid refresh."
        )
    return False, ""


def _begin_run(st: Any) -> None:
    _, maximum = estimate_request_range(st.session_state, preview_on=preview.preview_enabled(st))
    _RUN_CONTEXT.update(
        {
            "active": True,
            "limit": _configured_limit(maximum),
            "successful_requests": 0,
            "cache_hits": 0,
            "blocked_requests": 0,
            "request_log": [],
        }
    )


def _finish_run(st: Any, ran: bool) -> None:
    try:
        if ran:
            state = st.session_state
            minimum, maximum = estimate_request_range(state, preview_on=preview.preview_enabled(st))
            stats = {
                "successful_requests": int(_RUN_CONTEXT.get("successful_requests", 0) or 0),
                "cache_hits": int(_RUN_CONTEXT.get("cache_hits", 0) or 0),
                "blocked_requests": int(_RUN_CONTEXT.get("blocked_requests", 0) or 0),
                "limit": int(_RUN_CONTEXT.get("limit", 0) or 0),
                "estimated_min": minimum,
                "estimated_max": maximum,
                "preview_mode": bool(preview.preview_enabled(st)),
                "request_log": list(_RUN_CONTEXT.get("request_log", []) or []),
                "completed_at": time.time(),
            }
            state[LAST_STATS_KEY] = stats
            state[LAST_PROPERTY_KEY] = _current_property(state)
            state[LAST_PULL_EPOCH_KEY] = time.time()
    finally:
        _RUN_CONTEXT["active"] = False


def render_with_credit_guard(
    st: Any,
    ui: Any,
    original_renderer: Callable,
    exit_mode_value: str = "Auto",
) -> Any:
    before_normalized = st.session_state.get("one_load_normalized")
    before_run_at = st.session_state.get("decision_last_run_at")
    _begin_run(st)

    original_header = st.header

    def header_with_credit_panel(body: Any, *args: Any, **kwargs: Any):
        result = original_header(body, *args, **kwargs)
        if str(body or "").strip() == "Deal Decision Center":
            render_credit_panel(st)
        return result

    st.header = header_with_credit_panel

    delta_generator = None
    original_button = None
    try:
        try:
            from streamlit.delta_generator import DeltaGenerator

            delta_generator = DeltaGenerator
            original_button = DeltaGenerator.button

            def guarded_button(self: Any, label: str, *args: Any, **kwargs: Any):
                if str(label) == "Pull Everything & Tell Me":
                    disabled, reason = _button_should_be_disabled(st)
                    if disabled:
                        kwargs["disabled"] = True
                        if reason and not kwargs.get("help"):
                            kwargs["help"] = reason
                return original_button(self, label, *args, **kwargs)

            DeltaGenerator.button = guarded_button
        except Exception:
            delta_generator = None
            original_button = None

        return _ORIGINAL_DECISION_RENDER(st, ui, original_renderer, exit_mode_value)
    finally:
        st.header = original_header
        if delta_generator is not None and original_button is not None:
            delta_generator.button = original_button
        after_normalized = st.session_state.get("one_load_normalized")
        after_run_at = st.session_state.get("decision_last_run_at")
        activity = (
            after_normalized is not before_normalized
            or after_run_at != before_run_at
            or int(_RUN_CONTEXT.get("successful_requests", 0) or 0) > 0
            or int(_RUN_CONTEXT.get("cache_hits", 0) or 0) > 0
            or int(_RUN_CONTEXT.get("blocked_requests", 0) or 0) > 0
        )
        _finish_run(st, bool(activity and _current_property(st.session_state)))


def install() -> bool:
    if getattr(records, "_rentcast_credit_guard_installed", False):
        return True

    records._rentcast_credit_guard_original_request_json = _ORIGINAL_REQUEST_JSON
    rentcast._rentcast_credit_guard_original_get_json = _ORIGINAL_RENTCAST_GET_JSON
    bridge._rentcast_credit_guard_original_property_facts = _ORIGINAL_PROPERTY_FACTS
    decision_ui._rentcast_credit_guard_original_render = _ORIGINAL_DECISION_RENDER

    records._request_json = request_json_budgeted
    rentcast._get_json = rentcast_get_json_budgeted
    bridge._property_facts = property_facts_budgeted
    decision_ui.render = render_with_credit_guard

    # single_section_workspace imports deal_decision_ui.render at call time, but
    # keep both possible module aliases synchronized when already loaded.
    try:
        import sys

        for module_name in (
            "deal_decision_ui",
            "war_room_offer_engine.deal_decision_ui",
        ):
            loaded = sys.modules.get(module_name)
            if loaded is not None:
                loaded.render = render_with_credit_guard
    except Exception:
        pass

    records._rentcast_credit_guard_installed = True
    return True


install()

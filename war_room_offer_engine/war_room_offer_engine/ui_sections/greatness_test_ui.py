from __future__ import annotations


WEAK_ARV_CONFIDENCE = {"", "Missing", "Not enough data", "AVM only", "Weak", "Unknown"}
WEAK_RENT_CONFIDENCE = {"", "Missing", "Weak", "Weak / seller stated only", "Unknown"}
UNKNOWN_BUYER_DEMAND = {"", "Unknown", "No buyer list yet", "Weak", "Weak buyer list", "Limited buyer demand"}
SENSITIVE_PROTECTION_FIELDS = {
    "exact address",
    "seller/source details",
    "owner name",
    "listing agent phone/email",
    "listing/source links",
    "parcel ID/APN",
}


def _clean(value, default="Missing"):
    if value in [None, "", [], {}]:
        return default
    return value


def _money_label(value) -> str:
    try:
        return "${:,.0f}".format(float(value or 0))
    except Exception:
        return "$0"


def _status(label: str, status: str, detail: str) -> dict:
    return {"label": label, "status": status, "detail": detail}


def _is_clean_buy_answer(text: str) -> bool:
    normalized = str(text or "").lower()
    clean_buy_terms = ["buy", "proceed", "send offer", "make offer"]
    review_terms = ["human review", "analyze more", "verify", "teaser only", "pass", "renegotiate"]
    return any(term in normalized for term in clean_buy_terms) and not any(term in normalized for term in review_terms)


def _contains_sensitive_detail(message: str, state: dict) -> list[str]:
    message_lower = str(message or "").lower()
    leaks = []
    for key in ["address", "listing_url", "listing_agent_phone", "listing_agent_email", "owner_name", "seller_name"]:
        value = str(state.get(key) or "").strip()
        if value and value.lower() in message_lower:
            leaks.append(key)
    return leaks


def build_confidence_rollup(state: dict) -> dict:
    rent_confidence = str(state.get("rent_confidence") or state.get("manual_rent_confidence") or "Missing")
    arv_confidence = str(state.get("arv_confidence") or "Not enough data")
    buyer_demand = str(state.get("buyer_demand_confidence") or state.get("buyer_demand_score") or "Unknown")
    repair_confidence = str(state.get("repair_scope_confidence") or state.get("repair_confidence") or "Unknown")
    protection_allowed = str(state.get("buyer_message_allowed") or "Teaser Only")

    items = [
        _status("ARV", "Weak" if arv_confidence in WEAK_ARV_CONFIDENCE else "OK", arv_confidence),
        _status("Rent", "Weak" if rent_confidence in WEAK_RENT_CONFIDENCE else "OK", rent_confidence),
        _status("Buyer Demand", "Weak" if buyer_demand in UNKNOWN_BUYER_DEMAND else "OK", buyer_demand),
        _status("Repairs", "Review" if repair_confidence in ["Unknown", "Missing", "Photos only"] else "OK", repair_confidence),
        _status("Deal Protection", "OK" if protection_allowed in ["Teaser Only", "Full Blast Allowed"] else "Review", protection_allowed),
    ]
    weak_count = sum(1 for item in items if item["status"] == "Weak")
    review_count = sum(1 for item in items if item["status"] == "Review")
    if weak_count >= 2:
        overall = "Human Review Required"
    elif weak_count or review_count:
        overall = "Analyze More Before Offer"
    else:
        overall = "Ready for Manager Review"
    return {"overall": overall, "items": items, "weak_count": weak_count, "review_count": review_count}


def build_greatness_report(state: dict) -> dict:
    final_answer = str(state.get("one_load_final_answer") or state.get("final_decision") or state.get("simple_deal_answer") or "")
    best_exit = str(state.get("recommended_exit_strategy") or state.get("best_exit") or state.get("exit_mode") or "")
    rent_confidence = str(state.get("rent_confidence") or state.get("manual_rent_confidence") or "Missing")
    arv_confidence = str(state.get("arv_confidence") or "Not enough data")
    buyer_demand = str(state.get("buyer_demand_confidence") or state.get("buyer_demand_score") or "Unknown")
    protected_message = str(state.get("protected_buyer_message") or "")
    contract_status = str(state.get("contract_status") or "Not under contract")
    buyer_allowed = str(state.get("buyer_message_allowed") or "Teaser Only")
    hidden_fields = list(state.get("protected_fields_hidden") or [])
    exit_text = " ".join([best_exit, str(state.get("deal_type") or ""), str(state.get("exit_mode") or "")]).lower()

    issues = []
    checks = []

    clean_buy = _is_clean_buy_answer(final_answer)
    if clean_buy and arv_confidence in WEAK_ARV_CONFIDENCE:
        issues.append("Weak ARV blocks a clean Buy answer.")
        checks.append(_status("Weak ARV blocks clean Buy", "Fail", arv_confidence))
    else:
        checks.append(_status("Weak ARV blocks clean Buy", "OK", arv_confidence))

    if ("slow" in exit_text or str(state.get("deal_type") or "") == "Slow Flip Only") and rent_confidence in WEAK_RENT_CONFIDENCE:
        issues.append("Weak rent blocks clean Slow Flip approval.")
        checks.append(_status("Rent Fallback blocks clean Slow Flip", "Fail", rent_confidence))
    else:
        checks.append(_status("Rent Fallback blocks clean Slow Flip", "OK", rent_confidence))

    if "wholesale" in exit_text and buyer_demand in UNKNOWN_BUYER_DEMAND:
        issues.append("Unknown buyer demand blocks clean Wholesale approval.")
        checks.append(_status("Buyer demand blocks clean Wholesale", "Fail", buyer_demand))
    else:
        checks.append(_status("Buyer demand blocks clean Wholesale", "OK", buyer_demand))

    repair_text = " ".join(
        str(state.get(key) or "")
        for key in ["repair_scope_confidence", "repair_notes", "manual_repair_notes", "notes"]
    ).lower()
    risky_repairs = any(term in repair_text for term in ["foundation", "fire", "structural", "condemned", "termite"])
    if risky_repairs and clean_buy:
        issues.append("High repair or functional risk requires Human Review.")
        checks.append(_status("High repair risk requires Human Review", "Fail", "Clean answer with high repair risk"))
    else:
        checks.append(_status("High repair risk requires Human Review", "OK", "No clean approval leakage"))

    pre_contract = contract_status in ["Not under contract", "Offer sent", "Verbal agreement"]
    leaks = _contains_sensitive_detail(protected_message, state) if pre_contract else []
    required_hidden = sorted(SENSITIVE_PROTECTION_FIELDS - set(hidden_fields)) if pre_contract else []
    if pre_contract and (buyer_allowed != "Teaser Only" or leaks or required_hidden):
        issues.append("Deal Protection must hide sensitive details before contract.")
        detail = "; ".join(leaks + [f"missing hidden field: {field}" for field in required_hidden])
        checks.append(_status("Deal Protection pre-contract safety", "Fail", detail or buyer_allowed))
    else:
        checks.append(_status("Deal Protection pre-contract safety", "OK", buyer_allowed))

    if "mold" in protected_message.lower() and str(state.get("mold_verified") or "Unknown") not in ["Yes - inspector verified", "Yes - seller disclosed", "True", "true"]:
        issues.append("Protected buyer message uses mold wording without verification.")
        checks.append(_status("Mold wording guard", "Fail", "Unverified mold wording found"))
    else:
        checks.append(_status("Mold wording guard", "OK", "No unverified mold wording"))

    one_load_status = str(state.get("one_load_run_success") or "No")
    one_load_imported = list(state.get("one_load_imported_fields") or [])
    one_load_missing = list(state.get("one_load_missing_fields") or [])
    if one_load_status == "Yes" and not one_load_imported and one_load_missing:
        issues.append("One-Load parsed a lead but still needs analyzer field import/review.")
        checks.append(_status("One-Load import evidence", "Review", "Missing fields: " + ", ".join(one_load_missing[:5])))
    else:
        checks.append(_status("One-Load import evidence", "OK", f"Imported fields: {len(one_load_imported)}"))

    answer_checks = {
        "Should I buy this?": bool(final_answer),
        "At what price?": bool(state.get("asking_price") or state.get("contract_price") or state.get("one_load_final_answer")),
        "Why?": bool(state.get("decision_reason") or state.get("one_load_final_answer") or state.get("risk_flags")),
        "Best exit strategy": bool(best_exit),
        "What can go wrong?": bool(state.get("risk_flags") or state.get("exit_risk_warnings") or state.get("slow_flip_rent_risk")),
        "What is missing?": bool(state.get("missing_info") or state.get("one_load_missing_fields")),
        "What must be verified?": str(state.get("rent_verification_needed") or "Yes") == "Yes" or bool(state.get("exit_verification_items")),
        "Who might buy it?": bool(state.get("buyer_demand_confidence") or state.get("wholesale_buyer_list_strength")),
        "What should I do next?": bool(state.get("one_load_next_action") or state.get("team_action") or state.get("dispo_test_recommendation")),
    }
    missing_answer_checks = [label for label, ok in answer_checks.items() if not ok]
    if missing_answer_checks:
        checks.append(_status("Final answer quality", "Review", "Missing: " + ", ".join(missing_answer_checks)))
    else:
        checks.append(_status("Final answer quality", "OK", "All core questions have supporting data"))

    confidence = build_confidence_rollup(state)
    dashboard = {
        "qa_status": "Fail" if any(item["status"] == "Fail" for item in checks) else confidence["overall"],
        "confidence_rollup": confidence["overall"],
        "missing_answer_checks": missing_answer_checks,
        "issue_count": len(issues),
        "next_action": "Human Review" if issues else confidence["overall"],
    }
    return {"dashboard": dashboard, "confidence": confidence, "checks": checks, "issues": issues, "answer_checks": answer_checks}


def render_greatness_test_panel(st, ui) -> None:
    report = build_greatness_report(dict(st.session_state))
    dashboard = report["dashboard"]

    with st.expander("War Room Greatness Test / Full System QA", expanded=True):
        st.caption("Final safety check for confidence, missing information, deal protection, rent fallback, One-Load, and answer quality.")
        cols = st.columns(4)
        cols[0].metric("QA Status", dashboard["qa_status"])
        cols[1].metric("Confidence Rollup", dashboard["confidence_rollup"])
        cols[2].metric("Issues", dashboard["issue_count"])
        cols[3].metric("Next Action", dashboard["next_action"])

        st.markdown("#### Confidence Rollup")
        st.dataframe(report["confidence"]["items"], use_container_width=True, hide_index=True)

        st.markdown("#### System Checks")
        st.dataframe(report["checks"], use_container_width=True, hide_index=True)

        st.markdown("#### Final Answer Quality")
        quality_rows = [
            {"question": label, "covered": "Yes" if ok else "Needs info"}
            for label, ok in report["answer_checks"].items()
        ]
        st.dataframe(quality_rows, use_container_width=True, hide_index=True)

        if report["issues"]:
            for issue in report["issues"]:
                st.warning(issue)
        else:
            st.success("No greatness-test blockers found from the current session state.")

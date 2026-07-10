from __future__ import annotations

from typing import Any

try:
    from repair_price_book_il import (
        available_markets,
        available_repair_levels,
        detect_red_flags,
        estimate_scope,
        get_market_profile,
        get_market_multiplier,
        get_market_wholesale_buyer_percent,
        money,
        quick_scope_from_notes,
    )
except ImportError:
    try:
        from .repair_price_book_il import (
            available_markets,
            available_repair_levels,
            detect_red_flags,
            estimate_scope,
            get_market_profile,
            get_market_multiplier,
            get_market_wholesale_buyer_percent,
            money,
            quick_scope_from_notes,
        )
    except ImportError:
        try:
            from war_room_offer_engine.repair_price_book_il import (
                available_markets,
                available_repair_levels,
                detect_red_flags,
                estimate_scope,
                get_market_profile,
                get_market_multiplier,
                get_market_wholesale_buyer_percent,
                money,
                quick_scope_from_notes,
            )
        except ImportError:
            from war_room_offer_engine.war_room_offer_engine.repair_price_book_il import (
                available_markets,
                available_repair_levels,
                detect_red_flags,
                estimate_scope,
                get_market_profile,
                get_market_multiplier,
                get_market_wholesale_buyer_percent,
                money,
                quick_scope_from_notes,
            )


IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"]
VIDEO_EXTENSIONS = [".mp4", ".mov", ".m4v", ".avi"]


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def safe_condition_text(text: str, mold_verified: bool = False) -> str:
    if mold_verified:
        return str(text or "")
    replacements = {
        "black mold": "suspected biological growth",
        "mold remediation": "moisture/biological growth verification allowance",
        "visible mold": "visible discoloration",
        "mold": "moisture staining/discoloration",
    }
    clean = str(text or "")
    for old, new in replacements.items():
        clean = clean.replace(old, new)
        clean = clean.replace(old.title(), new)
        clean = clean.replace(old.upper(), new)
    return clean


def _pricing_mode_multiplier(category: str, item_key: str, pricing_mode: str) -> float:
    text = f"{category} {item_key}".lower()
    structural_terms = [
        "structural",
        "foundation",
        "termite",
        "wood",
        "moisture",
        "water",
        "electrical",
        "plumbing",
        "roof",
        "sewer",
        "crawlspace",
        "red flag",
    ]
    labor_heavy_terms = ["roof", "hvac", "plumbing", "electrical", "kitchen", "bath", "drywall", "flooring"]
    cosmetic_terms = ["interior", "paint", "flooring", "cleanout", "appliances", "safety", "exterior"]

    if pricing_mode == "Budget handyman":
        return 0.88 if any(term in text for term in cosmetic_terms) and not any(term in text for term in structural_terms) else 1.00
    if pricing_mode == "Licensed contractor":
        return 1.18 if any(term in text for term in labor_heavy_terms) else 1.08
    if pricing_mode == "Conservative high-risk":
        return 1.28 if any(term in text for term in structural_terms) else 1.12
    return 1.00


def _market_labor_multiplier(market_labor_cost: str) -> float:
    return {
        "Low-cost market": 0.94,
        "Normal market": 1.00,
        "High-cost market": 1.12,
        "Unknown": 1.06,
    }.get(market_labor_cost, 1.00)


def calibrate_repair_estimate(
    estimate: dict[str, Any],
    pricing_mode: str = "Investor standard",
    repair_scope_confidence: str = "Unknown",
    market_labor_cost: str = "Unknown",
    repair_cushion_percent: float = 0,
    manual_repair_adjustment: float = 0,
    mold_verified: bool = False,
) -> dict[str, Any]:
    base_total = safe_float(estimate.get("recommended_repair_number", 0))
    labor_multiplier = _market_labor_multiplier(market_labor_cost)
    rows = []
    pricing_adjustment_total = 0.0
    labor_adjustment_total = 0.0

    for item in estimate.get("line_items", []) or []:
        base_cost = safe_float(item.get("final_estimate", item.get("likely", 0)))
        pricing_multiplier = _pricing_mode_multiplier(
            category=str(item.get("category", "")),
            item_key=str(item.get("item_key", "")),
            pricing_mode=pricing_mode,
        )
        after_pricing = base_cost * pricing_multiplier
        after_labor = after_pricing * labor_multiplier
        pricing_adjustment = after_pricing - base_cost
        labor_adjustment = after_labor - after_pricing
        pricing_adjustment_total += pricing_adjustment
        labor_adjustment_total += labor_adjustment

        reason = pricing_mode
        if pricing_mode == "Budget handyman":
            reason = "Budget handyman pricing on cosmetic/non-structural scope"
        elif pricing_mode == "Licensed contractor":
            reason = "Licensed contractor pricing on labor-heavy scope"
        elif pricing_mode == "Conservative high-risk":
            reason = "Conservative high-risk pricing for unknown or red-flag scope"

        rows.append(
            {
                "Category": safe_condition_text(str(item.get("category", "")), mold_verified),
                "Reason": safe_condition_text(reason, mold_verified),
                "Base Cost": round(base_cost, 0),
                "Adjustment": round(pricing_adjustment + labor_adjustment, 0),
                "Final Cost": round(after_labor, 0),
                "Notes": safe_condition_text(str(item.get("notes", "")), mold_verified),
            }
        )

    subtotal_after_adjustments = sum(row["Final Cost"] for row in rows) if rows else base_total * labor_multiplier
    repair_risk_cushion = subtotal_after_adjustments * safe_float(repair_cushion_percent, 0) / 100
    final_repair_estimate = max(subtotal_after_adjustments + repair_risk_cushion + safe_float(manual_repair_adjustment, 0), 0)

    caution_warnings = []
    if repair_scope_confidence in ["Photos only", "Unknown"]:
        caution_warnings.append("Scope confidence is limited. Treat this as a working estimate until a walkthrough or contractor quote verifies it.")

    driver_labels = [
        safe_condition_text(str(row.get("Category", "")), mold_verified)
        for row in sorted(rows, key=lambda row: safe_float(row.get("Final Cost", 0)), reverse=True)[:5]
    ]
    driver_text = ", ".join(dict.fromkeys(label for label in driver_labels if label)) or "the entered repair scope"
    cushion_text = f" and a {safe_float(repair_cushion_percent, 0):.0f}% unknown-condition cushion" if safe_float(repair_cushion_percent, 0) else ""
    manual_text = ""
    if safe_float(manual_repair_adjustment, 0) > 0:
        manual_text = f", plus a manual add-on of {money(manual_repair_adjustment)}"
    elif safe_float(manual_repair_adjustment, 0) < 0:
        manual_text = f", minus a manual adjustment of {money(abs(safe_float(manual_repair_adjustment)))}"

    explanation = (
        f"Repairs are estimated at {money(final_repair_estimate)} because the app included {driver_text}, "
        f"used {pricing_mode.lower()} pricing, applied {market_labor_cost.lower()} labor assumptions"
        f"{cushion_text}{manual_text}."
    )

    return {
        "pricing_mode": pricing_mode,
        "repair_scope_confidence": repair_scope_confidence,
        "market_labor_cost": market_labor_cost,
        "repair_cushion_percent": safe_float(repair_cushion_percent, 0),
        "manual_repair_adjustment": safe_float(manual_repair_adjustment, 0),
        "base_repair_estimate": round(base_total, 0),
        "repair_pricing_adjustment": round(pricing_adjustment_total + labor_adjustment_total, 0),
        "market_labor_adjustment": round(labor_adjustment_total, 0),
        "repair_risk_cushion": round(repair_risk_cushion, 0),
        "final_repair_estimate": round(final_repair_estimate, 0),
        "repair_number_explanation": safe_condition_text(explanation, mold_verified),
        "repair_math_rows": rows,
        "caution_warnings": caution_warnings,
    }


def get_uploaded_file_name(file_obj: Any) -> str:
    return str(getattr(file_obj, "name", "") or "")


def get_uploaded_file_size(file_obj: Any) -> int:
    try:
        return int(getattr(file_obj, "size", 0) or 0)
    except Exception:
        return 0


def is_image_file(file_name: str) -> bool:
    name = str(file_name or "").lower()
    return any(name.endswith(ext) for ext in IMAGE_EXTENSIONS)


def is_video_file(file_name: str) -> bool:
    name = str(file_name or "").lower()
    return any(name.endswith(ext) for ext in VIDEO_EXTENSIONS)


def summarize_uploaded_files(uploaded_files: list[Any] | None) -> dict[str, Any]:
    uploaded_files = uploaded_files or []

    images = []
    videos = []
    other = []

    for file_obj in uploaded_files:
        name = get_uploaded_file_name(file_obj)
        size = get_uploaded_file_size(file_obj)

        row = {
            "name": name,
            "size": size,
        }

        if is_image_file(name):
            images.append(row)
        elif is_video_file(name):
            videos.append(row)
        else:
            other.append(row)

    return {
        "image_count": len(images),
        "video_count": len(videos),
        "other_count": len(other),
        "images": images,
        "videos": videos,
        "other": other,
        "total_files": len(uploaded_files),
    }


def add_file_based_allowance_if_needed(
    scope_items: list[dict[str, Any]],
    notes: str,
    file_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Photos/videos alone do not tell us exact repairs yet.
    Until we add true AI vision + video transcription, this adds a small safety allowance
    only when files are uploaded but notes did not create a repair scope.
    """

    if scope_items:
        return scope_items

    has_files = file_summary.get("image_count", 0) > 0 or file_summary.get("video_count", 0) > 0
    has_notes = bool(str(notes or "").strip())

    if has_files and not has_notes:
        return [
            {"item_key": "deep_clean", "quantity": 1},
            {"item_key": "locks_smoke_misc", "quantity": 1},
        ]

    return scope_items


def build_repair_scope_from_inputs(
    notes: str = "",
    sqft: float = 1000,
    baths: float = 1,
    uploaded_files: list[Any] | None = None,
) -> dict[str, Any]:
    file_summary = summarize_uploaded_files(uploaded_files)

    scope_items = quick_scope_from_notes(
        notes=notes,
        sqft=safe_float(sqft, 1000),
        baths=safe_float(baths, 1),
    )

    scope_items = add_file_based_allowance_if_needed(
        scope_items=scope_items,
        notes=notes,
        file_summary=file_summary,
    )

    red_flags = detect_red_flags(notes)

    return {
        "scope_items": scope_items,
        "file_summary": file_summary,
        "red_flags": red_flags,
    }


def analyze_repairs(
    notes: str = "",
    sqft: float = 1000,
    baths: float = 1,
    uploaded_files: list[Any] | None = None,
    market: str = "Central IL",
    repair_level: str = "Rental Ready",
    contingency_pct: float = 0.12,
    pricing_mode: str = "Investor standard",
    repair_scope_confidence: str = "Unknown",
    market_labor_cost: str = "Unknown",
    repair_cushion_percent: float = 0,
    manual_repair_adjustment: float = 0,
    mold_verified: bool = False,
) -> dict[str, Any]:
    if market not in available_markets():
        market = "Central IL"

    if repair_level not in available_repair_levels():
        repair_level = "Rental Ready"

    market_profile = get_market_profile(market)

    scope_result = build_repair_scope_from_inputs(
        notes=notes,
        sqft=sqft,
        baths=baths,
        uploaded_files=uploaded_files,
    )

    estimate = estimate_scope(
        scope_items=scope_result["scope_items"],
        market=market,
        repair_level=repair_level,
        contingency_pct=contingency_pct,
    )

    confidence = determine_confidence(
        notes=notes,
        file_summary=scope_result["file_summary"],
        red_flags=scope_result["red_flags"],
        line_items=estimate.get("line_items", []),
    )
    calibration = calibrate_repair_estimate(
        estimate=estimate,
        pricing_mode=pricing_mode,
        repair_scope_confidence=repair_scope_confidence,
        market_labor_cost=market_labor_cost,
        repair_cushion_percent=repair_cushion_percent,
        manual_repair_adjustment=manual_repair_adjustment,
        mold_verified=mold_verified,
    )

    return {
        "market": market,
        "market_profile": market_profile.get("buyer_profile", ""),
        "market_repair_multiplier": get_market_multiplier(market),
        "market_wholesale_buyer_percent_default": get_market_wholesale_buyer_percent(market),
        "repair_level": repair_level,
        "notes": notes,
        "scope_items": scope_result["scope_items"],
        "file_summary": scope_result["file_summary"],
        "red_flags": scope_result["red_flags"],
        "estimate": estimate,
        "repair_calibration": calibration,
        "confidence": confidence,
        "recommended_repair_number": calibration.get("final_repair_estimate", estimate.get("recommended_repair_number", 0)),
        "summary": build_summary_text(
            estimate=estimate,
            confidence=confidence,
            red_flags=scope_result["red_flags"],
            file_summary=scope_result["file_summary"],
        ),
    }


def determine_confidence(
    notes: str,
    file_summary: dict[str, Any],
    red_flags: list[str],
    line_items: list[dict[str, Any]],
) -> str:
    has_notes = bool(str(notes or "").strip())
    has_video = file_summary.get("video_count", 0) > 0
    has_images = file_summary.get("image_count", 0) > 0

    if red_flags:
        return "Low - red flags need contractor verification"

    if has_notes and (has_images or has_video) and line_items:
        return "Medium - based on notes plus uploaded media"

    if has_notes and line_items:
        return "Medium - based on boots-on-ground notes"

    if has_images or has_video:
        return "Low - media uploaded but no repair notes yet"

    return "Low - not enough repair information"


def build_summary_text(
    estimate: dict[str, Any],
    confidence: str,
    red_flags: list[str],
    file_summary: dict[str, Any],
) -> str:
    lines = []

    lines.append("Repair Estimate")
    lines.append(f"Market: {estimate.get('market', 'Central IL')}")
    lines.append(f"Repair level: {estimate.get('repair_level', 'Rental Ready')}")
    lines.append(f"Confidence: {confidence}")
    lines.append("")
    lines.append(f"Low: {money(estimate.get('total_low', 0))}")
    lines.append(f"Likely: {money(estimate.get('total_likely', 0))}")
    lines.append(f"High: {money(estimate.get('total_high', 0))}")
    lines.append(f"Recommended repair number: {money(estimate.get('recommended_repair_number', 0))}")
    lines.append("")

    lines.append(
        f"Files reviewed: {file_summary.get('image_count', 0)} photos, "
        f"{file_summary.get('video_count', 0)} videos"
    )

    if red_flags:
        lines.append("")
        lines.append("Red flags needing contractor quote:")
        for flag in red_flags:
            lines.append(f"- {flag}")

    line_items = estimate.get("line_items", [])
    if line_items:
        lines.append("")
        lines.append("Repair scope:")
        for item in line_items:
            lines.append(
                f"- {item.get('label')} | Qty: {item.get('quantity')} "
                f"{item.get('unit')} | Likely: {money(item.get('likely', 0))}"
            )

    return "\n".join(lines)


def repair_number_for_offer(analysis: dict[str, Any]) -> float:
    return safe_float(analysis.get("recommended_repair_number", 0), 0)

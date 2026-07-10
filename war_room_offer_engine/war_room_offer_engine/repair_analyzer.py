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
        "confidence": confidence,
        "recommended_repair_number": estimate.get("recommended_repair_number", 0),
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

from __future__ import annotations

import csv
import json
import re
from datetime import date, datetime, timedelta
from io import StringIO
from statistics import mean
from typing import Any


COMP_FIELDS = [
    "comp_address",
    "sold_price",
    "sold_date",
    "beds",
    "baths",
    "square_feet",
    "lot_size",
    "year_built",
    "property_type",
    "distance_miles",
    "condition",
    "source",
    "listing_url",
    "confidence",
    "notes",
]


COMP_ALIASES: dict[str, list[str]] = {
    "comp_address": ["comp_address", "address", "streetAddress", "fullAddress", "propertyAddress"],
    "sold_price": ["sold_price", "soldPrice", "lastSoldPrice", "lastSalePrice", "price", "unformattedPrice"],
    "sold_date": ["sold_date", "soldDate", "lastSoldDate", "lastSaleDate", "dateSold", "soldOn"],
    "beds": ["beds", "bedrooms"],
    "baths": ["baths", "bathrooms"],
    "square_feet": ["square_feet", "sqft", "livingArea", "livingAreaValue", "area"],
    "lot_size": ["lot_size", "lotSize", "lotAreaValue", "lotAreaString"],
    "year_built": ["year_built", "yearBuilt"],
    "property_type": ["property_type", "propertyType", "homeType"],
    "distance_miles": ["distance_miles", "distance", "distanceMiles"],
    "condition": ["condition", "homeCondition"],
    "source": ["source"],
    "listing_url": ["listing_url", "url", "detailUrl", "zillowUrl", "hdpUrl"],
    "confidence": ["confidence"],
    "notes": ["notes", "description", "remarks"],
}


def money_to_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value)
    if not text.strip():
        return 0.0
    multiplier = 1.0
    if re.search(r"\bm\b|million", text, re.IGNORECASE):
        multiplier = 1_000_000
    elif re.search(r"\bk\b", text, re.IGNORECASE):
        multiplier = 1_000
    cleaned = re.sub(r"[^0-9.\-]", "", text)
    try:
        return float(cleaned) * multiplier if cleaned else 0.0
    except Exception:
        return 0.0


def normalize_text(value: Any) -> str:
    return str(value or "").strip()


def get_value(record: dict[str, Any], aliases: list[str]) -> Any:
    lower_map = {str(key).lower(): key for key in record.keys()}
    for alias in aliases:
        key = lower_map.get(alias.lower())
        if key is not None and record.get(key) not in [None, "", [], {}]:
            return record.get(key)
    return None


def parse_date(value: Any) -> date | None:
    if value in [None, ""]:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)) and value > 10_000_000_000:
        return datetime.fromtimestamp(value / 1000).date()
    text = str(value).strip()
    for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%b %d %Y", "%B %d %Y"]:
        try:
            return datetime.strptime(text.replace(",", ""), fmt).date()
        except Exception:
            continue
    match = re.search(r"(20\d{2}|19\d{2})", text)
    if match:
        try:
            return date(int(match.group(1)), 1, 1)
        except Exception:
            return None
    return None


def sold_date_iso(value: Any) -> str:
    parsed = parse_date(value)
    return parsed.isoformat() if parsed else ""


def months_to_days(label: str) -> int:
    match = re.search(r"(\d+)", str(label or "12"))
    months = int(match.group(1)) if match else 12
    return months * 31


def radius_to_float(label: str) -> float:
    match = re.search(r"(\d+(?:\.\d+)?)", str(label or "1"))
    return float(match.group(1)) if match else 1.0


def normalize_sold_comp(record: dict[str, Any], source: str = "Unknown") -> dict[str, Any]:
    comp: dict[str, Any] = {}
    for field, aliases in COMP_ALIASES.items():
        value = get_value(record, aliases)
        if value in [None, "", [], {}]:
            continue
        comp[field] = value

    comp["comp_address"] = normalize_text(comp.get("comp_address"))
    comp["sold_price"] = money_to_float(comp.get("sold_price"))
    comp["sold_date"] = sold_date_iso(comp.get("sold_date"))
    comp["beds"] = money_to_float(comp.get("beds"))
    comp["baths"] = money_to_float(comp.get("baths"))
    comp["square_feet"] = money_to_float(comp.get("square_feet"))
    comp["year_built"] = money_to_float(comp.get("year_built"))
    comp["distance_miles"] = money_to_float(comp.get("distance_miles"))
    comp["lot_size"] = normalize_text(comp.get("lot_size"))
    comp["property_type"] = normalize_text(comp.get("property_type"))
    comp["condition"] = normalize_text(comp.get("condition"))
    comp["source"] = normalize_text(comp.get("source")) or source
    comp["listing_url"] = normalize_text(comp.get("listing_url"))
    comp["confidence"] = normalize_text(comp.get("confidence")) or "Medium"
    comp["notes"] = normalize_text(comp.get("notes"))
    return {field: comp.get(field, "" if field not in ["sold_price", "beds", "baths", "square_feet", "year_built", "distance_miles"] else 0) for field in COMP_FIELDS}


def normalize_sold_comps(records: list[dict[str, Any]], source: str = "Unknown") -> list[dict[str, Any]]:
    return [normalize_sold_comp(record, source=source) for record in records if isinstance(record, dict)]


def parse_comp_text(text: str, source: str = "Pasted text") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    text = str(text or "").strip()
    if not text:
        return rows
    try:
        reader = csv.DictReader(StringIO(text))
        if reader.fieldnames:
            return normalize_sold_comps(list(reader), source=source)
    except Exception:
        pass
    for line in text.splitlines():
        if not line.strip():
            continue
        price_match = re.search(r"\$?\s?([\d,]{4,})", line)
        date_match = re.search(r"(\d{1,2}/\d{1,2}/\d{2,4}|20\d{2}-\d{1,2}-\d{1,2})", line)
        sqft_match = re.search(r"([\d,]+)\s*(?:sqft|sq\.?\s*ft|sf)", line, re.IGNORECASE)
        beds_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:bed|br)", line, re.IGNORECASE)
        baths_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:bath|ba)", line, re.IGNORECASE)
        rows.append(
            normalize_sold_comp(
                {
                    "address": line.split("$")[0].strip(" ,-"),
                    "sold_price": price_match.group(1) if price_match else 0,
                    "sold_date": date_match.group(1) if date_match else "",
                    "sqft": sqft_match.group(1) if sqft_match else 0,
                    "beds": beds_match.group(1) if beds_match else 0,
                    "baths": baths_match.group(1) if baths_match else 0,
                    "notes": line,
                },
                source=source,
            )
        )
    return rows


def score_sold_comp(comp: dict[str, Any], subject: dict[str, Any], radius_miles: float, date_range_label: str) -> dict[str, Any]:
    flags: list[str] = []
    points = 100
    sold_price = money_to_float(comp.get("sold_price"))
    sold_date = parse_date(comp.get("sold_date"))
    sqft = money_to_float(comp.get("square_feet"))
    distance = money_to_float(comp.get("distance_miles"))
    subject_sqft = money_to_float(subject.get("sqft"))
    subject_beds = money_to_float(subject.get("beds"))
    subject_baths = money_to_float(subject.get("baths"))
    subject_type = normalize_text(subject.get("property_type")).lower()
    comp_type = normalize_text(comp.get("property_type")).lower()
    notes = normalize_text(comp.get("notes")).lower()

    if sold_price <= 0:
        flags.append("missing sold price")
        points -= 45
    if not sold_date:
        flags.append("missing sold date")
        points -= 25
    elif sold_date < date.today() - timedelta(days=months_to_days(date_range_label)):
        flags.append("older than selected date range")
        points -= 25
    if sqft <= 0:
        flags.append("missing sqft")
        points -= 25
    elif subject_sqft > 0 and abs(sqft - subject_sqft) / subject_sqft > 0.25:
        flags.append("sqft more than 25% different")
        points -= 20
    if distance > radius_miles:
        flags.append("too far away")
        points -= 25
    elif distance <= max(radius_miles, 0.01) / 2:
        points += 5
    if subject_type and comp_type and subject_type not in comp_type and comp_type not in subject_type:
        flags.append("different property type")
        points -= 20
    if subject_beds and comp.get("beds") and abs(money_to_float(comp.get("beds")) - subject_beds) > 1:
        flags.append("bed count mismatch")
        points -= 15
    if subject_baths and comp.get("baths") and abs(money_to_float(comp.get("baths")) - subject_baths) > 1:
        flags.append("bath count mismatch")
        points -= 10
    if any(term in notes for term in ["foreclosure", "reo", "auction", "as-is", "distressed", "bank owned", "short sale"]):
        flags.append("possible distressed sale")
        points -= 25
    if any(term in notes for term in ["fully renovated", "luxury", "new construction", "remodeled"]):
        flags.append("comp looks much better than subject")
        points -= 15
    if normalize_text(subject.get("functional_risks")):
        flags.append("subject has functional risks not reflected in comp")
        points -= 10
    source_confidence = normalize_text(comp.get("confidence")).lower()
    if "high" in source_confidence:
        points += 5
    elif "low" in source_confidence:
        points -= 10

    if points >= 85 and not flags:
        score = "Strong Comp"
    elif points >= 70:
        score = "Good Comp"
    elif points >= 45:
        score = "Weak Comp"
    else:
        score = "Bad Comp"

    return {**comp, "score": score, "score_points": max(min(points, 100), 0), "flags": flags, "include_default": score != "Bad Comp" and not any(flag.startswith("missing") for flag in flags)}


def apply_outlier_flags(scored: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prices = [money_to_float(comp.get("sold_price")) for comp in scored if money_to_float(comp.get("sold_price")) > 0]
    if len(prices) < 3:
        return scored
    avg = mean(prices)
    updated = []
    for comp in scored:
        price = money_to_float(comp.get("sold_price"))
        flags = list(comp.get("flags", []))
        points = int(comp.get("score_points", 0))
        if price > 0 and price < avg * 0.70:
            flags.append("very low outlier")
            points -= 20
        if price > 0 and price > avg * 1.35:
            flags.append("very high outlier")
            points -= 20
        score = comp.get("score", "Weak Comp")
        if points < 45:
            score = "Bad Comp"
        elif points < 70:
            score = "Weak Comp"
        elif points < 85:
            score = "Good Comp"
        updated.append({**comp, "flags": sorted(set(flags)), "score_points": max(points, 0), "score": score, "include_default": score != "Bad Comp" and not any(str(flag).startswith("missing") for flag in flags)})
    return updated


def score_sold_comps(comps: list[dict[str, Any]], subject: dict[str, Any], radius_label: str, date_range_label: str) -> list[dict[str, Any]]:
    radius = radius_to_float(radius_label)
    scored = [score_sold_comp(comp, subject, radius, date_range_label) for comp in comps]
    return apply_outlier_flags(scored)


def calculate_arv_from_comps(scored_comps: list[dict[str, Any]], included_keys: set[str] | None = None) -> dict[str, Any]:
    rows = []
    for idx, comp in enumerate(scored_comps):
        include = comp.get("include_default", False) if included_keys is None else str(idx) in included_keys
        if not include:
            continue
        price = money_to_float(comp.get("sold_price"))
        if price <= 0 or comp.get("score") == "Bad Comp":
            continue
        weight = {"Strong Comp": 1.5, "Good Comp": 1.0, "Weak Comp": 0.45}.get(comp.get("score"), 0)
        if weight > 0:
            rows.append((price, weight, comp))

    strong_count = sum(1 for comp in scored_comps if comp.get("score") == "Strong Comp")
    good_count = sum(1 for comp in scored_comps if comp.get("score") == "Good Comp")
    weak_count = sum(1 for comp in scored_comps if comp.get("score") == "Weak Comp")
    bad_count = sum(1 for comp in scored_comps if comp.get("score") == "Bad Comp")
    excluded_count = len(scored_comps) - len(rows)

    if not rows:
        return {
            "low_arv": 0,
            "conservative_arv": 0,
            "average_arv": 0,
            "high_arv": 0,
            "recommended_arv": 0,
            "arv_confidence": "Not enough data",
            "strong_comp_count": strong_count,
            "good_comp_count": good_count,
            "weak_comp_count": weak_count,
            "excluded_comp_count": excluded_count,
            "explanation": "No usable good sold comps were found.",
        }

    prices = [row[0] for row in rows]
    weighted = sum(price * weight for price, weight, _ in rows) / sum(weight for _, weight, _ in rows)
    good_or_strong = strong_count + good_count
    confidence = "Strong" if strong_count >= 2 and good_or_strong >= 3 else "Medium" if good_or_strong >= 3 else "Weak"
    return {
        "low_arv": round(min(prices), 0),
        "conservative_arv": round(sorted(prices)[max(0, int(len(prices) * 0.25) - 1)], 0),
        "average_arv": round(mean(prices), 0),
        "high_arv": round(max(prices), 0),
        "recommended_arv": round(weighted, 0),
        "arv_confidence": confidence,
        "strong_comp_count": strong_count,
        "good_comp_count": good_count,
        "weak_comp_count": weak_count,
        "excluded_comp_count": excluded_count,
        "explanation": f"Recommended ARV is based on {len(rows)} included sold comp(s), weighted toward strong and good comps.",
    }


def resolve_arv_fallback(
    manual_override: float = 0,
    manual_comp_average: float = 0,
    auto_summary: dict[str, Any] | None = None,
    rentcast_value: float = 0,
    zillow_value: float = 0,
    tax_assessed_value: float = 0,
) -> dict[str, Any]:
    auto_summary = auto_summary or {}
    warnings: list[str] = []
    if manual_override and manual_override > 0:
        warnings.append("Manual ARV override is active.")
        return {"arv": manual_override, "source": "Manual Override", "confidence": "Manual", "reason": "Manual ARV override has highest priority.", "warnings": warnings}
    if manual_comp_average and manual_comp_average > 0:
        return {"arv": manual_comp_average, "source": "Manual Comps", "confidence": "Manual", "reason": "Manual comp average is the highest available comp-based source.", "warnings": warnings}
    if auto_summary.get("recommended_arv", 0) > 0 and auto_summary.get("strong_comp_count", 0) > 0:
        confidence = auto_summary.get("arv_confidence", "Weak")
        if confidence == "Weak":
            warnings.append("ARV is weak because fewer than 3 good comps were found.")
        return {"arv": auto_summary["recommended_arv"], "source": "Automatic Sold Comps", "confidence": confidence, "reason": "Strong automatic sold comps are available.", "warnings": warnings}
    if auto_summary.get("recommended_arv", 0) > 0 and auto_summary.get("good_comp_count", 0) > 0:
        warnings.append("ARV is weak because fewer than 3 good comps were found.")
        return {"arv": auto_summary["recommended_arv"], "source": "Automatic Sold Comps", "confidence": "Weak", "reason": "Good automatic sold comps are available, but comp depth is limited.", "warnings": warnings}
    if rentcast_value and rentcast_value > 0:
        warnings.append("AVM used only as fallback, not final ARV.")
        return {"arv": rentcast_value, "source": "RentCast Estimate", "confidence": "AVM only", "reason": "RentCast value estimate used after comp sources were weak or missing.", "warnings": warnings}
    if zillow_value and zillow_value > 0:
        warnings.append("AVM used only as fallback, not final ARV.")
        return {"arv": zillow_value, "source": "Zillow/Apify AVM", "confidence": "AVM only", "reason": "Zillow/Apify AVM used after comp sources were weak or missing.", "warnings": warnings}
    if tax_assessed_value and tax_assessed_value > 0:
        warnings.append("Tax assessment is not ARV. Use only as reference.")
        return {"arv": tax_assessed_value, "source": "Tax Assessment Reference", "confidence": "Reference only", "reason": "Tax assessment used only as a low-confidence reference.", "warnings": warnings}
    return {"arv": 0, "source": "Missing", "confidence": "Not enough data", "reason": "No ARV source is available. Needs Human Review.", "warnings": ["ARV is missing. Add ARV or manual comps before making a final offer."]}


def comp_summary_json(scored_comps: list[dict[str, Any]]) -> str:
    return json.dumps(scored_comps, default=str)


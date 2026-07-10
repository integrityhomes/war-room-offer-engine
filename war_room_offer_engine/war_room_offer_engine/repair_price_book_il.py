from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RepairPrice:
    category: str
    label: str
    unit: str
    low: float
    likely: float
    high: float
    notes: str = ""


@dataclass
class MarketProfile:
    group: str
    buyer_profile: str
    repair_multiplier: float
    wholesale_buyer_percent: float
    notes: str = ""


# NON-CHICAGO ILLINOIS INVESTOR PRICING ONLY.
# These are working numbers for quick acquisition analysis, not final contractor bids.
# We will tune these over time from Shawn/Sabrina's real contractor invoices.
REPAIR_PRICE_BOOK: dict[str, RepairPrice] = {
    # Roof / exterior
    "roof_full_replace": RepairPrice(
        "Roof",
        "Full asphalt shingle roof replacement",
        "sqft_roof",
        4.25,
        5.50,
        7.00,
        "Investor-grade non-Chicago IL roof pricing. Use roof surface area, not interior sq ft.",
    ),
    "roof_patch": RepairPrice(
        "Roof",
        "Roof patch / leak repair",
        "each",
        600,
        1250,
        2500,
        "Use for localized roof leaks or missing shingles.",
    ),
    "gutters": RepairPrice(
        "Exterior",
        "Gutters / downspouts",
        "linear_ft",
        6,
        9,
        13,
        "Basic aluminum gutters and downspouts.",
    ),
    "siding_patch": RepairPrice(
        "Exterior",
        "Siding patch / exterior trim repair",
        "each",
        500,
        1200,
        2500,
        "Use for localized exterior repairs.",
    ),
    "windows": RepairPrice(
        "Exterior",
        "Basic vinyl window replacement",
        "each",
        350,
        550,
        850,
        "Basic rental/investor-grade replacement window.",
    ),
    "exterior_doors": RepairPrice(
        "Exterior",
        "Exterior door replacement",
        "each",
        450,
        800,
        1400,
        "Basic entry door, hardware not premium.",
    ),

    # HVAC / mechanicals
    "furnace": RepairPrice(
        "HVAC",
        "Furnace replacement",
        "each",
        2800,
        4000,
        6000,
        "Basic non-Chicago IL furnace replacement.",
    ),
    "ac": RepairPrice(
        "HVAC",
        "Central AC replacement",
        "each",
        3200,
        4750,
        7000,
        "Basic condenser/AC replacement.",
    ),
    "hvac_full": RepairPrice(
        "HVAC",
        "Full HVAC system replacement",
        "each",
        6000,
        8500,
        12000,
        "Furnace + AC basic system. Flag for contractor quote.",
    ),

    # Plumbing
    "water_heater": RepairPrice(
        "Plumbing",
        "Water heater replacement",
        "each",
        1000,
        1500,
        2300,
        "Basic tank water heater replacement.",
    ),
    "plumbing_minor": RepairPrice(
        "Plumbing",
        "Minor plumbing repairs",
        "each",
        400,
        1000,
        2500,
        "Leaks, traps, valves, basic fixture corrections.",
    ),
    "plumbing_supply_rework": RepairPrice(
        "Plumbing",
        "Supply/drain line rework",
        "each",
        1500,
        3500,
        7500,
        "Use for larger plumbing corrections. Flag if major.",
    ),

    # Electrical
    "electrical_minor": RepairPrice(
        "Electrical",
        "Minor electrical repairs",
        "each",
        400,
        1200,
        3000,
        "Switches, outlets, fixtures, basic corrections.",
    ),
    "electrical_panel": RepairPrice(
        "Electrical",
        "Electrical panel replacement",
        "each",
        1500,
        2500,
        4000,
        "Flag for licensed electrician quote.",
    ),
    "rewire_heavy": RepairPrice(
        "Electrical",
        "Heavy electrical rewire allowance",
        "sqft",
        4.00,
        6.50,
        10.00,
        "Use cautiously. Always flag knob/tube, fire damage, or unsafe wiring.",
    ),

    # Interior surfaces
    "paint_interior": RepairPrice(
        "Interior",
        "Interior paint",
        "sqft",
        1.25,
        2.00,
        3.00,
        "Investor-grade paint allowance using house sq ft.",
    ),
    "drywall_patch": RepairPrice(
        "Interior",
        "Drywall patching",
        "each",
        250,
        600,
        1500,
        "Localized patching.",
    ),
    "drywall_heavy": RepairPrice(
        "Interior",
        "Heavy drywall repair allowance",
        "sqft",
        1.50,
        2.50,
        4.00,
        "Use house sq ft as rough allowance for heavy wall/ceiling work.",
    ),
    "flooring_lvp": RepairPrice(
        "Interior",
        "LVP / basic hard surface flooring",
        "sqft",
        3.50,
        5.50,
        8.00,
        "Investor-grade LVP or similar.",
    ),
    "flooring_carpet": RepairPrice(
        "Interior",
        "Basic carpet replacement",
        "sqft",
        2.25,
        3.50,
        5.50,
        "Investor-grade carpet.",
    ),
    "subfloor_repair": RepairPrice(
        "Interior",
        "Subfloor repair allowance",
        "each",
        500,
        1500,
        4000,
        "Soft floors/water damaged areas. Flag if widespread.",
    ),

    # Kitchen / bath
    "kitchen_basic": RepairPrice(
        "Kitchen",
        "Basic kitchen refresh",
        "each",
        4500,
        8000,
        14000,
        "Cabinets/counters/sink/faucet/basic finish allowance.",
    ),
    "kitchen_heavy": RepairPrice(
        "Kitchen",
        "Heavy kitchen renovation",
        "each",
        9000,
        15000,
        25000,
        "Use if cabinets, counters, plumbing, electrical, and flooring all need work.",
    ),
    "bath_basic": RepairPrice(
        "Bathroom",
        "Basic bathroom refresh",
        "each",
        3000,
        5500,
        9000,
        "Vanity, toilet, basic tub/surround/flooring/paint allowance.",
    ),
    "bath_heavy": RepairPrice(
        "Bathroom",
        "Heavy bathroom renovation",
        "each",
        6500,
        10000,
        16000,
        "Use if subfloor/plumbing/tub/tile/full gut is needed.",
    ),

    # Cleanout / appliances / safety
    "trashout": RepairPrice(
        "Cleanout",
        "Trash out / debris removal",
        "each",
        600,
        1500,
        3500,
        "Depends on volume and access.",
    ),
    "deep_clean": RepairPrice(
        "Cleanout",
        "Deep clean",
        "each",
        300,
        700,
        1400,
        "Basic post-trash-out cleaning.",
    ),
    "appliance_package": RepairPrice(
        "Appliances",
        "Basic appliance package",
        "each",
        1800,
        2800,
        4500,
        "Used/basic new appliance package.",
    ),
    "locks_smoke_misc": RepairPrice(
        "Safety",
        "Locks, smoke detectors, misc safety items",
        "each",
        250,
        600,
        1200,
        "Basic make-ready safety allowance.",
    ),

    # Red-flag allowances
    "mold_water_damage": RepairPrice(
        "Red Flag",
        "Mold / water damage allowance",
        "each",
        1500,
        5000,
        15000,
        "Needs contractor inspection if visible mold or active water intrusion.",
    ),
    "foundation_structural": RepairPrice(
        "Red Flag",
        "Foundation / structural allowance",
        "each",
        3000,
        10000,
        30000,
        "Always flag for contractor quote.",
    ),
        "sewer_line": RepairPrice(
        "Red Flag",
        "Sewer line allowance",
        "each",
        2500,
        6500,
        15000,
        "Always flag for sewer scope if suspected.",
    ),

    "crawlspace_vapor_barrier": RepairPrice(
        "Virginia / Crawlspace",
        "Crawlspace vapor barrier / moisture control",
        "each",
        1200,
        2500,
        6000,
        "Virginia crawlspaces often need moisture control, vapor barrier, and possible wood repair.",
    ),
        "termite_treatment": RepairPrice(
        "Virginia / Pest",
        "Termite treatment / wood-destroying insect allowance",
        "each",
        750,
        1800,
        4500,
        "Use when termite activity, fungus, or wood rot is mentioned. Contractor verification required.",
    ),
    "septic_inspection_allowance": RepairPrice(
        "Virginia / Septic",
        "Septic inspection / pump / minor allowance",
        "each",
        500,
        1200,
        3500,
        "Use for rural Virginia properties when septic is unknown or needs verification.",
    ),
    "well_inspection_allowance": RepairPrice(
        "Virginia / Well",
        "Well inspection / water test allowance",
        "each",
        350,
        900,
        2500,
        "Use for rural Virginia properties with a well or unknown water source.",
    ),
    "oil_tank_allowance": RepairPrice(
        "Virginia / HVAC",
        "Oil heat / oil tank inspection allowance",
        "each",
        750,
        2500,
        8000,
        "Use when oil heat or oil tank is mentioned. Underground tanks can become a major issue.",
    ),
    "fuse_box_panel_upgrade": RepairPrice(
        "Virginia / Electrical",
        "Fuse box / old panel upgrade allowance",
        "each",
        1800,
        3500,
        7500,
        "Use when fuse box, knob and tube, aluminum wiring, or old electrical panel is mentioned.",
    ),
    "active_roof_leak_water_intrusion": RepairPrice(
        "Virginia / Red Flag",
        "Active roof leak / water intrusion allowance",
        "each",
        1500,
        4500,
        12000,
        "Red-flag allowance only. Active leaks require contractor verification.",
    ),
    "mold_remediation_allowance": RepairPrice(
        "Virginia / Red Flag",
        "Mold remediation allowance",
        "each",
        2500,
        7500,
        20000,
        "Investor-grade allowance. Visible mold requires contractor verification.",
    ),
    "crawlspace_wood_rot_repair": RepairPrice(
        "Virginia / Crawlspace",
        "Crawlspace wood rot repair",
        "each",
        2500,
        7500,
        18000,
        "Use for crawlspace moisture, fungus, or localized wood rot. Contractor verification required.",
    ),
    "floor_joist_sill_plate_repair": RepairPrice(
        "Virginia / Structural",
        "Floor joist / sill plate repair allowance",
        "each",
        3500,
        9500,
        25000,
        "Structural red flag. Use only as a working estimate until contractor verification.",
    ),
    "polybutylene_plumbing_allowance": RepairPrice(
        "Virginia / Plumbing",
        "Polybutylene plumbing allowance",
        "each",
        3500,
        8500,
        18000,
        "Use when polybutylene is present or suspected. Contractor verification required.",
    ),
    "galvanized_plumbing_allowance": RepairPrice(
        "Virginia / Plumbing",
        "Galvanized plumbing allowance",
        "each",
        2500,
        6500,
        16000,
        "Use when old galvanized supply lines are present or suspected.",
    ),
    "heat_pump_replacement": RepairPrice(
        "Virginia / HVAC",
        "Heat pump replacement",
        "each",
        5500,
        8500,
        14000,
        "Common Virginia HVAC allowance. Confirm tonnage and ductwork condition.",
    ),
    "mobile_manufactured_home_repair": RepairPrice(
        "Virginia / Specialty",
        "Mobile/manufactured home repair allowance",
        "each",
        3500,
        10000,
        25000,
        "Use for manufactured-home-specific access, skirting, roof, floor, or system issues.",
    ),
    "rural_driveway_gravel_access": RepairPrice(
        "Virginia / Rural",
        "Rural driveway / gravel / access allowance",
        "each",
        1000,
        3500,
        10000,
        "Use for long gravel driveways, access issues, or rural site cleanup.",
    ),
    "flood_zone_moisture_risk": RepairPrice(
        "Virginia / Red Flag",
        "Flood zone / moisture risk allowance",
        "each",
        1500,
        5000,
        15000,
        "Risk allowance only. Verify flood zone, drainage, and moisture history before offer.",
    ),
}




MARKET_PROFILES: dict[str, MarketProfile] = {
    # Illinois - non-Chicago investor pricing
    "Downstate IL": MarketProfile("Illinois", "Rural / thin buyer market", 0.95, 0.64),
    "Central IL": MarketProfile("Illinois", "Normal investor market", 1.00, 0.69),
    "Metro East IL": MarketProfile("Illinois / St. Louis Metro", "Normal investor market", 1.05, 0.70),
    "Northern IL Non-Chicago": MarketProfile("Illinois", "Normal investor market", 1.10, 0.70),

    # Virginia investor pricing
    "Southside VA": MarketProfile("Virginia", "Rural / thin buyer market", 1.03, 0.63),
    "Southwest VA": MarketProfile("Virginia", "Rural / thin buyer market", 1.00, 0.62),
    "Roanoke / Lynchburg VA": MarketProfile("Virginia", "Normal investor market", 1.05, 0.68),
    "Richmond / Petersburg VA": MarketProfile("Virginia", "Strong / liquid market", 1.12, 0.73),
    "Hampton Roads / Tidewater VA": MarketProfile("Virginia", "Strong / liquid market", 1.15, 0.73),
    "Shenandoah Valley VA": MarketProfile("Virginia", "Normal investor market", 1.08, 0.68),
    "Charlottesville / Central VA": MarketProfile("Virginia", "Strong / liquid market", 1.15, 0.74),
    "Fredericksburg / Northern Neck VA": MarketProfile("Virginia", "Strong / liquid market", 1.18, 0.74),
    "Eastern Shore VA": MarketProfile("Virginia", "Rural / thin buyer market", 1.12, 0.63),
    "Northern VA": MarketProfile("Virginia", "Strong / liquid market", 1.35, 0.75),

    # Michigan
    "Detroit Metro MI": MarketProfile("Michigan", "Strong / liquid market", 1.08, 0.73),
    "Flint / Saginaw MI": MarketProfile("Michigan", "Normal investor market", 0.98, 0.68),
    "Lansing MI": MarketProfile("Michigan", "Normal investor market", 1.02, 0.69),
    "Kalamazoo / Battle Creek MI": MarketProfile("Michigan", "Normal investor market", 1.03, 0.69),
    "Grand Rapids MI": MarketProfile("Michigan", "Strong / liquid market", 1.10, 0.73),
    "Rural Michigan": MarketProfile("Michigan", "Rural / thin buyer market", 0.95, 0.62),

    # St. Louis Metro
    "St. Louis City MO": MarketProfile("St. Louis Metro", "Normal investor market", 1.04, 0.69),
    "North St. Louis County MO": MarketProfile("St. Louis Metro", "Normal investor market", 1.02, 0.68),
    "South St. Louis County MO": MarketProfile("St. Louis Metro", "Strong / liquid market", 1.06, 0.72),
    "St. Charles / West County MO": MarketProfile("St. Louis Metro", "Strong / liquid market", 1.12, 0.74),

    # Indiana
    "Indianapolis IN": MarketProfile("Indiana", "Strong / liquid market", 1.04, 0.72),
    "Fort Wayne IN": MarketProfile("Indiana", "Normal investor market", 0.98, 0.69),
    "South Bend IN": MarketProfile("Indiana", "Normal investor market", 1.00, 0.68),
    "Evansville IN": MarketProfile("Indiana", "Normal investor market", 0.96, 0.68),
    "Gary / Northwest IN": MarketProfile("Indiana", "Normal investor market", 1.03, 0.68),
    "Rural Indiana": MarketProfile("Indiana", "Rural / thin buyer market", 0.92, 0.62),

    # Alabama
    "Birmingham AL": MarketProfile("Alabama", "Strong / liquid market", 0.95, 0.72),
    "Montgomery AL": MarketProfile("Alabama", "Normal investor market", 0.90, 0.68),
    "Mobile AL": MarketProfile("Alabama", "Normal investor market", 0.94, 0.69),
    "Huntsville AL": MarketProfile("Alabama", "Strong / liquid market", 1.02, 0.74),
    "Tuscaloosa AL": MarketProfile("Alabama", "Normal investor market", 0.93, 0.69),
    "Rural Alabama": MarketProfile("Alabama", "Rural / thin buyer market", 0.88, 0.62),

    # Florida
    "Jacksonville FL": MarketProfile("Florida", "Strong / liquid market", 1.12, 0.73),
    "Tampa Bay FL": MarketProfile("Florida", "Strong / liquid market", 1.22, 0.75),
    "Orlando FL": MarketProfile("Florida", "Strong / liquid market", 1.18, 0.74),
    "Ocala / Gainesville FL": MarketProfile("Florida", "Normal investor market", 1.10, 0.69),
    "Panhandle FL": MarketProfile("Florida", "Normal investor market", 1.08, 0.68),
    "South Florida FL": MarketProfile("Florida", "Strong / liquid market", 1.32, 0.75),
    "Rural Florida": MarketProfile("Florida", "Rural / thin buyer market", 1.05, 0.64),
}


MARKET_MULTIPLIERS = {
    market: profile.repair_multiplier for market, profile in MARKET_PROFILES.items()
}

   


REPAIR_LEVEL_MULTIPLIERS = {
    "Investor Basic": 0.90,
    "Rental Ready": 1.00,
    "Retail Ready": 1.25,
}


RED_FLAG_KEYWORDS = [
    "foundation",
    "structural",
    "bowing",
    "settling",
    "mold",
    "black mold",
    "fire damage",
    "burned",
    "sewer",
    "main line",
    "collapsed pipe",
    "knob and tube",
    "termite",
    "flood",
    "water intrusion",
    "active leak",
    "crawlspace",
    "crawl space",
    "moisture",
    "standing water",
    "fungus",
    "termite",
    "termites",
    "wood rot",
    "well",
    "septic",
    "oil heat",
    "oil tank",
    "fuse box",
    "knob and tube",
    "aluminum wiring",
    "galvanized plumbing",
    "polybutylene",
    "coastal humidity",
    "flood zone",
    "pier foundation",
    "active roof leak",
    "roof leak",
    "water intrusion",
    "crawlspace wood rot",
    "floor joist",
    "sill plate",
    "heat pump",
    "mobile home",
    "manufactured home",
    "rural driveway",
    "gravel driveway",
    "access issue",
]


def money(value: float) -> str:
    return f"${float(value):,.0f}"


def get_market_multiplier(market: str) -> float:
    return MARKET_MULTIPLIERS.get(market, 1.00)


def get_market_profile(market: str) -> dict[str, Any]:
    profile = MARKET_PROFILES.get(market) or MARKET_PROFILES["Central IL"]
    return {
        "market": market if market in MARKET_PROFILES else "Central IL",
        "group": profile.group,
        "buyer_profile": profile.buyer_profile,
        "repair_multiplier": profile.repair_multiplier,
        "wholesale_buyer_percent": profile.wholesale_buyer_percent,
        "notes": profile.notes,
    }


def get_market_wholesale_buyer_percent(market: str) -> float:
    return get_market_profile(market).get("wholesale_buyer_percent", 0.70)


def get_market_repair_multiplier(market: str) -> float:
    return get_market_multiplier(market)


def get_level_multiplier(level: str) -> float:
    return REPAIR_LEVEL_MULTIPLIERS.get(level, 1.00)


def available_markets() -> list[str]:
    return list(MARKET_PROFILES.keys())


def available_repair_levels() -> list[str]:
    return list(REPAIR_LEVEL_MULTIPLIERS.keys())


def available_repair_items() -> list[dict[str, str]]:
    rows = []
    for key, item in REPAIR_PRICE_BOOK.items():
        rows.append(
            {
                "key": key,
                "category": item.category,
                "label": item.label,
                "unit": item.unit,
            }
        )
    return rows


def estimate_line_item(
    item_key: str,
    quantity: float = 1,
    market: str = "Central IL",
    repair_level: str = "Rental Ready",
) -> dict[str, Any]:
    item = REPAIR_PRICE_BOOK[item_key]
    qty = max(float(quantity or 0), 0)

    market_mult = get_market_multiplier(market)
    level_mult = get_level_multiplier(repair_level)
    multiplier = market_mult * level_mult

    low = item.low * qty * multiplier
    likely = item.likely * qty * multiplier
    high = item.high * qty * multiplier

    return {
        "item_key": item_key,
        "category": item.category,
        "label": item.label,
        "unit": item.unit,
        "quantity": qty,
        "low": round(low, 0),
        "likely": round(likely, 0),
        "high": round(high, 0),
        "notes": item.notes,
    }


def estimate_scope(
    scope_items: list[dict[str, Any]],
    market: str = "Central IL",
    repair_level: str = "Rental Ready",
    contingency_pct: float = 0.12,
) -> dict[str, Any]:
    line_items = []

    for row in scope_items:
        item_key = row.get("item_key")
        quantity = row.get("quantity", 1)

        if item_key not in REPAIR_PRICE_BOOK:
            continue

        line_items.append(
            estimate_line_item(
                item_key=item_key,
                quantity=quantity,
                market=market,
                repair_level=repair_level,
            )
        )

    subtotal_low = sum(row["low"] for row in line_items)
    subtotal_likely = sum(row["likely"] for row in line_items)
    subtotal_high = sum(row["high"] for row in line_items)

    contingency_low = subtotal_low * contingency_pct
    contingency_likely = subtotal_likely * contingency_pct
    contingency_high = subtotal_high * contingency_pct

    total_low = subtotal_low + contingency_low
    total_likely = subtotal_likely + contingency_likely
    total_high = subtotal_high + contingency_high

    return {
        "market": market,
        "repair_level": repair_level,
        "contingency_pct": contingency_pct,
        "line_items": line_items,
        "subtotal_low": round(subtotal_low, 0),
        "subtotal_likely": round(subtotal_likely, 0),
        "subtotal_high": round(subtotal_high, 0),
        "total_low": round(total_low, 0),
        "total_likely": round(total_likely, 0),
        "total_high": round(total_high, 0),
        "recommended_repair_number": round(total_likely, 0),
    }


def detect_red_flags(notes: str) -> list[str]:
    text = str(notes or "").lower()
    flags = []

    for keyword in RED_FLAG_KEYWORDS:
        if keyword in text:
            flags.append(keyword)

    return sorted(set(flags))


def quick_scope_from_notes(notes: str, sqft: float = 1000, baths: float = 1) -> list[dict[str, Any]]:
    """
    Simple keyword-based scope builder.
    This is not the AI vision/video analyzer yet.
    It helps the app create a starting repair estimate from boots-on-ground notes.
    """

    text = str(notes or "").lower()
    house_sqft = float(sqft or 1000)
    bath_count = max(float(baths or 1), 1)

    scope: list[dict[str, Any]] = []

    def add(item_key: str, quantity: float = 1):
        if item_key in REPAIR_PRICE_BOOK:
            scope.append({"item_key": item_key, "quantity": quantity})

    # Roof / exterior
    if any(word in text for word in ["roof", "shingle", "leak in roof"]):
        if any(word in text for word in ["full roof", "needs roof", "bad roof", "roof shot", "replace roof"]):
            add("roof_full_replace", house_sqft * 1.15)
        else:
            add("roof_patch", 1)

    if "gutter" in text or "downspout" in text:
        add("gutters", 120)

    if "window" in text:
        add("windows", 4)

    if "siding" in text or "fascia" in text or "soffit" in text:
        add("siding_patch", 1)

    if "door" in text:
        add("exterior_doors", 1)

    # Mechanicals
    if "water heater" in text or "hot water tank" in text:
        add("water_heater", 1)

    if "furnace" in text:
        add("furnace", 1)

    if "air conditioner" in text or " ac " in f" {text} " or "central air" in text:
        add("ac", 1)

    if "hvac" in text or "heating and air" in text:
        add("hvac_full", 1)

    if "heat pump" in text:
        add("heat_pump_replacement", 1)

    if "electrical panel" in text or "breaker panel" in text or "fuse box" in text:
        add("electrical_panel", 1)

    if "electrical" in text or "outlets" in text or "wiring" in text:
        add("electrical_minor", 1)

    if "plumbing" in text or "leak" in text or "pipes" in text:
        add("plumbing_minor", 1)

    if "supply line" in text or "drain line" in text or "pipes need replaced" in text:
        add("plumbing_supply_rework", 1)

    if "polybutylene" in text:
        add("polybutylene_plumbing_allowance", 1)

    if "galvanized" in text:
        add("galvanized_plumbing_allowance", 1)

    # Interior
    if "paint" in text:
        add("paint_interior", house_sqft)

    if "drywall" in text or "holes in wall" in text or "ceiling damage" in text:
        if "heavy drywall" in text or "a lot of drywall" in text or "walls are bad" in text:
            add("drywall_heavy", house_sqft)
        else:
            add("drywall_patch", 3)

    if "floor" in text or "flooring" in text or "carpet" in text or "lvp" in text:
        if "carpet" in text:
            add("flooring_carpet", house_sqft * 0.75)
        else:
            add("flooring_lvp", house_sqft * 0.75)

    if "soft floor" in text or "subfloor" in text:
        add("subfloor_repair", 1)

    if "floor joist" in text or "sill plate" in text:
        add("floor_joist_sill_plate_repair", 1)

    # Kitchen / bath
    if "kitchen" in text:
        if "gut kitchen" in text or "full kitchen" in text or "kitchen is destroyed" in text:
            add("kitchen_heavy", 1)
        else:
            add("kitchen_basic", 1)

    if "bathroom" in text or "bath" in text:
        if "gut bath" in text or "full bath" in text or "bathroom is destroyed" in text:
            add("bath_heavy", bath_count)
        else:
            add("bath_basic", bath_count)

    # Cleanout / safety
    if "trash" in text or "junk" in text or "debris" in text or "clean out" in text:
        add("trashout", 1)

    if "dirty" in text or "cleaning" in text or "deep clean" in text:
        add("deep_clean", 1)

    if "appliance" in text or "stove" in text or "fridge" in text or "refrigerator" in text:
        add("appliance_package", 1)

    if "lock" in text or "smoke detector" in text or "safety" in text:
        add("locks_smoke_misc", 1)

    # Red flags
    if "mold" in text or "water damage" in text:
        add("mold_water_damage", 1)

    if "foundation" in text or "structural" in text or "bowing" in text:
        add("foundation_structural", 1)

    if "sewer" in text:
        add("sewer_line", 1)

    if "active roof leak" in text or "water intrusion" in text or ("roof" in text and "leak" in text):
        add("active_roof_leak_water_intrusion", 1)

    if "mold remediation" in text or "black mold" in text:
        add("mold_remediation_allowance", 1)

    if "crawlspace" in text or "crawl space" in text:
        add("crawlspace_vapor_barrier", 1)

    if "wood rot" in text or "fungus" in text:
        add("crawlspace_wood_rot_repair", 1)

    if "termite" in text or "termites" in text:
        add("termite_treatment", 1)

    if "septic" in text:
        add("septic_inspection_allowance", 1)

    if "well" in text:
        add("well_inspection_allowance", 1)

    if "oil heat" in text or "oil tank" in text:
        add("oil_tank_allowance", 1)

    if "fuse box" in text or "knob and tube" in text or "aluminum wiring" in text:
        add("fuse_box_panel_upgrade", 1)

    if "mobile home" in text or "manufactured home" in text:
        add("mobile_manufactured_home_repair", 1)

    if "gravel driveway" in text or "rural driveway" in text or "access issue" in text:
        add("rural_driveway_gravel_access", 1)

    if "flood zone" in text or "moisture risk" in text:
        add("flood_zone_moisture_risk", 1)

    # If notes are empty or too vague, give a small safety allowance.
    if not scope and text.strip():
        add("locks_smoke_misc", 1)
        add("deep_clean", 1)

    return scope


def summarize_estimate(estimate: dict[str, Any]) -> str:
    lines = [
        f"Market: {estimate.get('market')}",
        f"Repair level: {estimate.get('repair_level')}",
        f"Low: {money(estimate.get('total_low', 0))}",
        f"Likely: {money(estimate.get('total_likely', 0))}",
        f"High: {money(estimate.get('total_high', 0))}",
        f"Recommended repair number: {money(estimate.get('recommended_repair_number', 0))}",
    ]

    return "\n".join(lines)

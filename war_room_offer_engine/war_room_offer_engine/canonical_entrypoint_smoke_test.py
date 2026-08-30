from __future__ import annotations

from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent.parent
ROOT_APP = REPO_ROOT / "app.py"
CANONICAL_APP = APP_DIR / "app.py"


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"OK: {message}")


def main() -> None:
    root_source = ROOT_APP.read_text(encoding="utf-8")
    check(CANONICAL_APP.exists(), "canonical nested Offer Engine app exists")
    check("runpy.run_path" in root_source, "root app is a compatibility launcher")
    check(
        '"war_room_offer_engine"' in root_source and '"app.py"' in root_source,
        "root launcher targets the nested production app",
    )
    check("FIELD_DEFAULTS" not in root_source, "root app does not carry a second property-state implementation")
    check("analyze_deal" not in root_source, "root app does not carry duplicate offer-analysis logic")


if __name__ == "__main__":
    main()

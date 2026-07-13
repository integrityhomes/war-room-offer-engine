from __future__ import annotations

from pathlib import Path


APP_DIR = Path(__file__).resolve().parent


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"OK: {message}")


guard_text = (APP_DIR / "ui_runtime_guard.py").read_text(encoding="utf-8")
repair_text = (APP_DIR / "ui_sections" / "repair_ui.py").read_text(encoding="utf-8")
loader_text = (APP_DIR / "one_load_sources_safe.py").read_text(encoding="utf-8")

check("reset_state_value" in guard_text, "state guard uses safe Streamlit reset instead of crashing")
check("AUTO_PULL_WIDGET_KEYS" in guard_text, "state guard is limited to known auto-pull fields")
check("Quick Tools" in guard_text, "sidebar quick tools are rendered")
check("Repairs & Walkthrough" in guard_text, "sidebar includes repair shortcut")
check("Buyer Outreach / Dispo" in guard_text, "sidebar includes buyer outreach shortcut")
check("Greatness Test / QA" in guard_text, "sidebar includes QA shortcut")
check("import ui_runtime_guard" in loader_text or "from . import ui_runtime_guard" in loader_text, "runtime guard loads before One-Load")
check('st.header("🔧 Repairs & Property Condition")' in repair_text, "repair workspace has a clear full-width heading")
check('id="repairs"' in repair_text, "repair workspace has a direct navigation anchor")
check("Upload property photos or boots-on-ground walkthrough video" in repair_text, "repair media upload remains available")
check("Generate boots-on-ground notes from media" in repair_text, "media note generation remains available")
check("Generate Repair Estimate" in repair_text, "repair estimate action remains available")
check("Manual repair estimate override" in repair_text, "manual repair override remains available")
check("render_comps_section(st, ui)" in repair_text, "sold comps and ARV remain connected")

print("UI navigation, state guard, and repair workspace smoke test passed.")

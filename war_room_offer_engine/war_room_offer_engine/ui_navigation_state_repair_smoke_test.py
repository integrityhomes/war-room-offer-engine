from __future__ import annotations

from pathlib import Path


APP_DIR = Path(__file__).resolve().parent


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"OK: {message}")


outreach_ui_text = (APP_DIR / "ui_sections" / "realtor_outreach_ui.py").read_text(encoding="utf-8")
repair_text = (APP_DIR / "ui_sections" / "repair_ui.py").read_text(encoding="utf-8")

check("_war_room_pending_auto_pull" in outreach_ui_text, "late auto-pull data is queued instead of crashing")
check("_install_lead_intake_guard_from_caller" in outreach_ui_text, "Property Data is guarded before widgets render")
check("st.rerun()" in outreach_ui_text, "queued data triggers a safe rerun")
check("Quick Tools" in outreach_ui_text, "Quick Tools are rendered")
check('("🛠️", "Repairs", "3-repair-condition-analyzer")' in outreach_ui_text, "Quick Tools includes Repairs")
check('("🏘️", "Comps / ARV", "automatic-sold-comps")' in outreach_ui_text, "Quick Tools includes comps and ARV")
check("wr-tool-dock" in outreach_ui_text, "desktop side tool boxes are styled and visible")
check("with st.sidebar" in outreach_ui_text, "sidebar navigation is also available")
check('st.header("🔧 Repairs & Property Condition")' in repair_text, "repair workspace has a clear full-width heading")
check('id="repairs"' in repair_text, "repair workspace has a direct navigation anchor")
check("Upload property photos or boots-on-ground walkthrough video" in repair_text, "repair media upload remains available")
check("Generate boots-on-ground notes from media" in repair_text, "media note generation remains available")
check("Generate Repair Estimate" in repair_text, "repair estimate action remains available")
check("Manual repair estimate override" in repair_text, "manual repair override remains available")
check("render_comps_section(st, ui)" in repair_text, "sold comps and ARV remain connected")

print("UI navigation, state-order guard, and repair workspace smoke test passed.")

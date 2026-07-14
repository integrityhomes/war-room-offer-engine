from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace


APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent.parent
for import_path in [str(REPO_ROOT), str(APP_DIR), str(APP_DIR / "ui_sections")]:
    if import_path in sys.path:
        sys.path.remove(import_path)
    sys.path.insert(0, import_path)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"OK: {message}")


workspace = importlib.import_module("single_section_workspace")


class FakeState(dict):
    pass


class FakeSt:
    def __init__(self):
        self.session_state = FakeState()


fake_st = FakeSt()
check(workspace.active_section(fake_st) == "One-Load", "One-Load is the default section")
check(len(workspace.SECTION_OPTIONS) == 9, "all nine workspace tools are available")
check(len(set(workspace.RENDER_SECTION_MAP.values())) == 8, "each primary renderer has one workspace section")

calls: list[str] = []
workspace._render_decision_center = lambda *args, **kwargs: calls.append("Deal Decision Center")
namespace = {
    "render_one_load_deal_section": lambda *args, **kwargs: calls.append("Legacy One-Load"),
    "render_lead_intake_section": lambda *args, **kwargs: calls.append("Pull Data"),
    "render_deal_protection_section": lambda *args, **kwargs: calls.append("Protection"),
    "render_rent_fallback_section": lambda *args, **kwargs: calls.append("Rent"),
    "render_buyer_demand_section": lambda *args, **kwargs: calls.append("Buyer Demand"),
    "render_buyer_outreach_section": lambda *args, **kwargs: calls.append("Dispo"),
    "render_repair_section": lambda *args, **kwargs: calls.append("Repairs") or ["upload"],
    "render_decision_section": lambda *args, **kwargs: calls.append("QA / Decision"),
}

for name in workspace.RENDER_SECTION_MAP:
    workspace._wrap_renderer(namespace, name, fake_st)

namespace["render_one_load_deal_section"](fake_st, SimpleNamespace())
namespace["render_lead_intake_section"](fake_st, SimpleNamespace())
namespace["render_repair_section"](fake_st, SimpleNamespace())
check(calls == ["Deal Decision Center"], "One-Load opens the simplified Deal Decision Center")

fake_st.session_state["war_room_active_section"] = "🛠️ Repairs"
repair_result = namespace["render_repair_section"](fake_st, SimpleNamespace())
namespace["render_one_load_deal_section"](fake_st, SimpleNamespace())
check(calls[-1] == "Repairs", "selecting Repairs opens the repair workspace")
check(repair_result == ["upload"], "active Repairs preserves uploaded media return value")

fake_st.session_state["repair_media_files"] = ["saved-file"]
fake_st.session_state["war_room_active_section"] = "🏠 One-Load"
hidden_repair_result = namespace["render_repair_section"](fake_st, SimpleNamespace())
check(hidden_repair_result == ["saved-file"], "closed Repairs preserves saved media for decision math")
check(workspace.SECTION_NAMES["🏘️ Comps / ARV"] == "Comps / ARV", "Comps and ARV remains separate")
check(workspace.SECTION_NAMES["✅ QA / Decision"] == "QA / Decision", "QA and Decision remains separate")

print("Single-section workspace smoke test passed.")

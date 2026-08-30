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
        self.captions: list[str] = []

    def caption(self, text: str) -> None:
        self.captions.append(text)


fake_st = FakeSt()
check(workspace.active_section(fake_st) == "One-Load", "Analyze Deal is the default work area")
check(len(workspace.SECTION_OPTIONS) == 10, "all ten stable workspace values remain available")
check(
    workspace.WORKSPACE_OPTIONS[:3] == ["🏠 One-Load", "📡 Listing Radar", "✅ QA / Decision"],
    "daily work destinations appear first without changing stable values",
)
check(workspace.SECTION_DISPLAY_LABELS["🏠 One-Load"] == "🏠 Analyze Deal", "One-Load displays as Analyze Deal")
check(workspace.SECTION_DISPLAY_LABELS["✅ QA / Decision"] == "✅ Decision & Save", "QA/Decision displays as Decision & Save")
check(workspace.SECTION_NAMES["🏠 One-Load"] == "One-Load", "One-Load keeps its stabilized routing value")
check(workspace.SECTION_NAMES["📡 Listing Radar"] == "Listing Radar", "Listing Radar keeps its stabilized routing value")
check(len(set(workspace.RENDER_SECTION_MAP.values())) == 8, "each primary renderer has one workspace section")

# Stable sessions must continue to reopen the exact same underlying workspace.
fake_st.session_state["war_room_active_section"] = "🛠️ Repairs"
check(workspace.active_section(fake_st) == "Repairs", "existing Repairs session value remains compatible")
# Friendly values from the usability branch also fail safely back to the stable value.
fake_st.session_state["war_room_active_section"] = "🛠️ Repair Estimate"
check(workspace.active_section(fake_st) == "Repairs", "friendly Repair Estimate value migrates to stable Repairs")
fake_st.session_state.clear()

selector_calls = []
workspace.render_workspace_selector(
    fake_st,
    lambda label, options, **kwargs: selector_calls.append((label, list(options), kwargs)) or options[0],
)
workspace.render_workspace_selector(
    fake_st,
    lambda label, options, **kwargs: selector_calls.append((label, list(options), kwargs)) or options[0],
)
check(len(selector_calls) == 1, "work-area selector renders exactly once per rerun")
check(selector_calls[0][0] == "Work area", "selector uses a plain-English label")
check(selector_calls[0][1] == workspace.WORKSPACE_OPTIONS, "selector uses the daily-work-first order")
check(selector_calls[0][2].get("key") == "war_room_active_section", "selector preserves its session key")
format_func = selector_calls[0][2].get("format_func")
check(callable(format_func), "selector formats stable values with friendly labels")
check(format_func("🏠 One-Load") == "🏠 Analyze Deal", "selector visibly says Analyze Deal")
check("normal deal work" in fake_st.captions[-1], "default work area explains where normal deal work starts")

routing_st = FakeSt()
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
    workspace._wrap_renderer(namespace, name, routing_st)

routing_st.session_state["war_room_active_section"] = "🏠 One-Load"
namespace["render_one_load_deal_section"](routing_st, SimpleNamespace())
namespace["render_lead_intake_section"](routing_st, SimpleNamespace())
namespace["render_repair_section"](routing_st, SimpleNamespace())
check(
    "Deal Decision Center" in calls and "Legacy One-Load" not in calls,
    f"Analyze Deal opens the simplified Deal Decision Center; calls={calls!r}",
)

before_listing = list(calls)
routing_st.session_state["war_room_active_section"] = "📡 Listing Radar"
namespace["render_one_load_deal_section"](routing_st, SimpleNamespace())
namespace["render_lead_intake_section"](routing_st, SimpleNamespace())
namespace["render_repair_section"](routing_st, SimpleNamespace())
check(calls == before_listing, "Listing Radar suppresses property-analysis renderers")

routing_st.session_state["war_room_active_section"] = "🛠️ Repairs"
repair_result = namespace["render_repair_section"](routing_st, SimpleNamespace())
namespace["render_one_load_deal_section"](routing_st, SimpleNamespace())
check(calls[-1] == "Repairs", "Repair Estimate opens the existing repair workspace")
check(repair_result == ["upload"], "active Repair Estimate preserves uploaded media return value")

routing_st.session_state["repair_media_files"] = ["saved-file"]
routing_st.session_state["war_room_active_section"] = "🏠 One-Load"
hidden_repair_result = namespace["render_repair_section"](routing_st, SimpleNamespace())
check(hidden_repair_result == ["saved-file"], "closed repair workspace preserves saved media for decision math")
check(workspace.SECTION_NAMES["🏘️ Comps / ARV"] == "Comps / ARV", "Comps & Value keeps the existing comp engine")
check(workspace.SECTION_NAMES["✅ QA / Decision"] == "QA / Decision", "Decision & Save keeps the existing decision engine")

print("Single-section workspace smoke test passed.")

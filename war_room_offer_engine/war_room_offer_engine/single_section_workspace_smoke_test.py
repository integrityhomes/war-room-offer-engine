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
check(len(workspace.SECTION_OPTIONS) == 10, "all ten workspace tools remain available")
check(
    workspace.SECTION_OPTIONS[:3] == ["🏠 Analyze Deal", "📡 Listing Radar", "✅ Decision & Save"],
    "daily work destinations appear first",
)
check(workspace.SECTION_NAMES["🏠 Analyze Deal"] == "One-Load", "Analyze Deal keeps the One-Load engine")
check(workspace.SECTION_NAMES["📡 Listing Radar"] == "Listing Radar", "Listing Radar keeps its stable section name")
check(workspace.SECTION_NAMES["✅ Decision & Save"] == "QA / Decision", "Decision & Save keeps the QA/Decision engine")
check(len(set(workspace.RENDER_SECTION_MAP.values())) == 8, "each primary renderer has one workspace section")

# A session saved under the old developer-facing label must still reopen the
# same underlying workspace instead of dropping the operator into a new deal.
fake_st.session_state["war_room_active_section"] = "🛠️ Repairs"
check(workspace.active_section(fake_st) == "Repairs", "legacy Repairs session label remains compatible")
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
check(selector_calls[0][1] == workspace.SECTION_OPTIONS, "selector exposes all work areas")
check(selector_calls[0][2].get("key") == "war_room_active_section", "selector preserves its session key")
check("Analyze Deal" in fake_st.captions[-1], "default work area explains where normal deal work starts")

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

fake_st.session_state["war_room_active_section"] = "🏠 Analyze Deal"
namespace["render_one_load_deal_section"](fake_st, SimpleNamespace())
namespace["render_lead_intake_section"](fake_st, SimpleNamespace())
namespace["render_repair_section"](fake_st, SimpleNamespace())
check(calls == ["Deal Decision Center"], "Analyze Deal opens the simplified Deal Decision Center")

fake_st.session_state["war_room_active_section"] = "📡 Listing Radar"
namespace["render_one_load_deal_section"](fake_st, SimpleNamespace())
namespace["render_lead_intake_section"](fake_st, SimpleNamespace())
namespace["render_repair_section"](fake_st, SimpleNamespace())
check(calls == ["Deal Decision Center"], "Listing Radar suppresses property-analysis renderers")

fake_st.session_state["war_room_active_section"] = "🛠️ Repair Estimate"
repair_result = namespace["render_repair_section"](fake_st, SimpleNamespace())
namespace["render_one_load_deal_section"](fake_st, SimpleNamespace())
check(calls[-1] == "Repairs", "Repair Estimate opens the existing repair workspace")
check(repair_result == ["upload"], "active Repair Estimate preserves uploaded media return value")

fake_st.session_state["repair_media_files"] = ["saved-file"]
fake_st.session_state["war_room_active_section"] = "🏠 Analyze Deal"
hidden_repair_result = namespace["render_repair_section"](fake_st, SimpleNamespace())
check(hidden_repair_result == ["saved-file"], "closed repair workspace preserves saved media for decision math")
check(workspace.SECTION_NAMES["🏘️ Comps & Value"] == "Comps / ARV", "Comps & Value keeps the existing comp engine")
check(workspace.SECTION_NAMES["✅ Decision & Save"] == "QA / Decision", "Decision & Save keeps the existing decision engine")

print("Single-section workspace smoke test passed.")

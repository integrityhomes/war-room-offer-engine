from __future__ import annotations

import importlib
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent.parent
for import_path in [str(REPO_ROOT), str(APP_DIR)]:
    if import_path in sys.path:
        sys.path.remove(import_path)
    sys.path.insert(0, import_path)


workspace = importlib.import_module("workspace_mode")


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"OK: {message}")


class FakeSt:
    def __init__(self, selected: str):
        self.session_state = {workspace.WORKSPACE_KEY: selected}


calls: list[str] = []


def original_renderer(*args, **kwargs):
    calls.append("rendered")
    return "result"


check(workspace.DEFAULT_WORKSPACE == "🏠 One-Load", "One-Load is the default workspace")
check(len(workspace.WORKSPACE_OPTIONS) == len(set(workspace.WORKSPACE_OPTIONS)), "workspace options are unique")
check("🛠️ Repairs" in workspace.WORKSPACE_OPTIONS, "Repairs remains available")
check("🏘️ Comps / ARV" in workspace.WORKSPACE_OPTIONS, "Comps and ARV remain available")
check("✅ QA / Decision" in workspace.WORKSPACE_OPTIONS, "QA and Decision remain available")

one_load_guard = workspace._make_workspace_guard("render_one_load_deal_section", original_renderer)
result = one_load_guard(FakeSt("🏠 One-Load"), object())
check(result == "result" and calls == ["rendered"], "selected One-Load renderer opens")

calls.clear()
result = one_load_guard(FakeSt("🛠️ Repairs"), object())
check(result is None and not calls, "unselected One-Load renderer stays closed")

repair_guard = workspace._make_workspace_guard("render_repair_section", original_renderer)
calls.clear()
result = repair_guard(FakeSt("🛠️ Repairs"), object())
check(result == "result" and calls == ["rendered"], "selected Repairs workspace opens")

calls.clear()
result = repair_guard(FakeSt("🏷️ Rent"), object())
check(result == [] and not calls, "unselected repair renderer returns a safe empty upload list")

embedded_comps_calls: list[str] = []
repair_only_calls: list[str] = []


def render_comps_section(*args, **kwargs):
    embedded_comps_calls.append("comps")


def repair_renderer_with_embedded_comps(*args, **kwargs):
    repair_only_calls.append("repairs")
    render_comps_section(*args, **kwargs)
    return ["upload"]


separated_repair_guard = workspace._make_workspace_guard(
    "render_repair_section",
    repair_renderer_with_embedded_comps,
)
result = separated_repair_guard(FakeSt("🛠️ Repairs"), object())
check(result == ["upload"] and repair_only_calls == ["repairs"], "Repairs workspace still runs the repair renderer")
check(not embedded_comps_calls, "Repairs workspace does not also open Comps / ARV")

check(
    workspace.RENDERER_WORKSPACES["render_decision_section"] == "✅ QA / Decision",
    "Decision renderer is isolated to the QA workspace",
)
check(
    workspace.RENDERER_WORKSPACES["render_lead_intake_section"] == "🔎 Pull Data",
    "Property Data has its own workspace",
)

source_text = (APP_DIR / "workspace_mode.py").read_text(encoding="utf-8")
loader_text = (APP_DIR / "one_load_sources_safe.py").read_text(encoding="utf-8")
check("position: fixed" not in source_text, "new navigation does not create a right-side floating panel")
check("_inside_old_quick_tools" in source_text, "older floating and duplicate navigation is suppressed")
check("Only that section stays open" in source_text, "sidebar explains single-section behavior")
check("_render_repairs_without_comps" in source_text, "repair and comps workspaces are separated")
check("import workspace_mode" in loader_text, "workspace mode loads during app startup")

print("Sidebar single-section workspace smoke test passed.")

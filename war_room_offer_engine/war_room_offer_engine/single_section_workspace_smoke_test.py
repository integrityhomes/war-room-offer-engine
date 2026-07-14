from __future__ import annotations

from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
workspace_text = (APP_DIR / "single_section_workspace.py").read_text(encoding="utf-8")
loader_text = (APP_DIR / "one_load_sources_safe.py").read_text(encoding="utf-8")


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"OK: {message}")


check('DEFAULT_TOOL = TOOL_OPTIONS[0]' in workspace_text, "One-Load is the default workspace")
check('"🏠 One-Load"' in workspace_text, "One-Load menu option exists")
check('"🔎 Pull Data"' in workspace_text, "Pull Data menu option exists")
check('"🛠️ Repairs"' in workspace_text, "Repairs menu option exists")
check('"🏘️ Comps / ARV"' in workspace_text, "Comps and ARV menu option exists")
check('"✅ QA / Decision"' in workspace_text, "QA and Decision menu option exists")
check('key="war_room_active_tool"' in workspace_text, "one persistent workspace selector controls the app")
check('label_visibility="collapsed"' in workspace_text, "workspace selector uses a clean card-style menu")
check('_install_renderer_guards' in workspace_text, "section renderers are guarded")
check('active_tool(st) == "🏠 One-Load"' in workspace_text, "One-Load only renders when selected")
check('active_tool(st_arg) != "🔎 Pull Data"' in workspace_text, "Pull Data only renders when selected")
check('selected != "🛠️ Repairs"' in workspace_text, "Repairs only renders when selected")
check('selected == "🏘️ Comps / ARV"' in workspace_text, "Comps and ARV render separately")
check('active_tool(st) == "✅ QA / Decision"' in workspace_text, "QA and Decision only render when selected")
check('_preserve_workspace_state' in workspace_text, "deal inputs persist while switching workspaces")
check('_war_room_repair_media_cache' in workspace_text, "repair media is cached for Decision")
check('st._war_room_quick_tools_title_hook = True' in workspace_text, "old anchor-link navigation is disabled")
check('wr-tool-dock' not in workspace_text, "new workspace controller has no floating right-side panel")
check('import single_section_workspace' in loader_text, "workspace controller loads with One-Load")

print("Single-section workspace smoke test passed.")

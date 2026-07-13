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


def import_first(*module_names: str):
    last_error: Exception | None = None
    for module_name in module_names:
        try:
            return importlib.import_module(module_name)
        except ImportError as exc:
            last_error = exc
    raise last_error or ImportError("No module names provided")


module = import_first(
    "realtor_outreach_ui",
    "ui_sections.realtor_outreach_ui",
    "war_room_offer_engine.ui_sections.realtor_outreach_ui",
    "war_room_offer_engine.war_room_offer_engine.ui_sections.realtor_outreach_ui",
)


class FakeState(dict):
    def pop(self, key, default=None):
        return super().pop(key, default)


class RerunRequested(RuntimeError):
    pass


class FakeSt:
    def __init__(self):
        self.session_state = FakeState()

    def rerun(self):
        raise RerunRequested("rerun")


class FakeStreamlitAPIException(RuntimeError):
    pass


fake_st = FakeSt()
applied: list[dict] = []


def failing_update(data: dict) -> None:
    raise FakeStreamlitAPIException(
        'st.session_state["listing_url"] cannot be modified after the widget with key "listing_url" is instantiated.'
    )


def install_from_caller():
    ui = SimpleNamespace(update_state_from_auto_pull=failing_update)
    module._install_safe_auto_pull_state_order(fake_st)
    return ui


ui = install_from_caller()
try:
    ui.update_state_from_auto_pull({"listing_url": "https://www.zillow.com/test", "asking_price": 65000})
except RerunRequested:
    pass
else:
    raise AssertionError("state-order conflict should request a rerun")

check(
    fake_st.session_state.get("_war_room_pending_auto_pull", {}).get("asking_price") == 65000,
    "late auto-pull values are queued instead of crashing",
)
check(
    module._is_widget_state_order_error(FakeStreamlitAPIException("cannot be modified after the widget with key")),
    "Streamlit widget state-order error is recognized",
)
check(
    any(label == "Repairs" and anchor == "3-repair-condition-analyzer" for _, label, anchor in module._QUICK_TOOLS),
    "Quick Tools includes a direct Repairs jump",
)
check(
    any(label == "One-Load" for _, label, _ in module._QUICK_TOOLS),
    "Quick Tools includes One-Load",
)
check(
    any(label == "QA / Decision" for _, label, _ in module._QUICK_TOOLS),
    "Quick Tools includes QA and decision",
)
check(
    len({anchor for _, _, anchor in module._QUICK_TOOLS}) == len(module._QUICK_TOOLS),
    "Quick Tool anchors are unique",
)

print("Auto-pull state-order and Quick Tools smoke test passed.")

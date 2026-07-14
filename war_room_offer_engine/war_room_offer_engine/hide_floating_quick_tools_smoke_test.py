from __future__ import annotations

import importlib.util
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
patch_path = APP_DIR / "hide_floating_quick_tools.py"
source_text = (APP_DIR / "one_load_sources_safe.py").read_text(encoding="utf-8")

spec = importlib.util.spec_from_file_location("hide_floating_quick_tools_test", patch_path)
module = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
spec.loader.exec_module(module)

floating_html = '<div class="wr-tool-dock"><div class="wr-tool-title">Quick Tools</div></div>'
sidebar_link = '[🏠 **One-Load**](#one-load-deal-analyzer)'

assert module.is_floating_quick_tools_html(floating_html)
assert not module.is_floating_quick_tools_html(sidebar_link)
assert "hide_floating_quick_tools" in source_text
assert "with st.sidebar" not in patch_path.read_text(encoding="utf-8")
assert "css_injected" not in patch_path.read_text(encoding="utf-8")

print("Floating Quick Tools panel regression smoke test passed.")

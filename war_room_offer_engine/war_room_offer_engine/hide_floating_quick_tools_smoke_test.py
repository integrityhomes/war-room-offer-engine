from __future__ import annotations

from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
patch_text = (APP_DIR / "hide_floating_quick_tools.py").read_text(encoding="utf-8")
source_text = (APP_DIR / "one_load_sources_safe.py").read_text(encoding="utf-8")

assert ".wr-tool-dock{display:none!important;}" in patch_text
assert "hide_floating_quick_tools" in source_text
assert "with st.sidebar" not in patch_text

print("Floating Quick Tools panel hide patch smoke test passed.")

from pathlib import Path

root = Path(__file__).resolve().parent
text = (root / "one_load_sources_safe.py").read_text(encoding="utf-8")

workspace_pos = text.find("import single_section_workspace")
hide_pos = text.find("import hide_floating_quick_tools")

assert workspace_pos >= 0, "single-section workspace import is missing"
assert hide_pos >= 0, "floating Quick Tools hide import is missing"
assert workspace_pos < hide_pos, "floating Quick Tools hide patch must load after workspace switcher"
assert "apply last so the right-side floating panel stays hidden" in text

print("Floating Quick Tools load-order smoke test passed.")

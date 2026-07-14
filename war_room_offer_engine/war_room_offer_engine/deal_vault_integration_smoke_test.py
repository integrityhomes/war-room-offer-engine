from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent
source = (ROOT / "deal_decision_ui.py").read_text(encoding="utf-8")

assert "vault.apply_pending_snapshot(st)" in source
assert source.index("vault.apply_pending_snapshot(st)") < source.index("initialize(st)")
assert "vault.render_box(st, media_files=media or [])" in source
assert "vault.find_saved_before_pull(st, property_input)" in source
assert source.index("vault.find_saved_before_pull(st, property_input)") < source.index("_run(st, ui, media or [])")
assert "No property-data credits were used" in source
assert "vault.save_current(st, media_files=media_files, automatic=True)" in source
assert "deal_vault_force_live_refresh" in source

requirements = (ROOT.parent.parent / "requirements.txt").read_text(encoding="utf-8")
assert "google-auth" in requirements

print("Deal Vault load-before-paid-pull, auto-save, restore order, and dependency smoke test passed.")

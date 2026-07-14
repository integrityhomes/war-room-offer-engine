from __future__ import annotations

from deal_vault_google_sheets import (
    HISTORY_HEADERS,
    HISTORY_TAB,
    VAULT_HEADERS,
    VAULT_TAB,
    DealVaultSheets,
)
from deal_vault_snapshot import build_snapshot, summary_from_state


class MemoryVault(DealVaultSheets):
    def __init__(self):
        super().__init__("test-sheet", {"client_email": "test@example.com", "private_key": "test"})
        self.records = []
        self.history = []

    def ensure_ready(self):
        return None

    def list_deals(self):
        output = []
        for index, record in enumerate(self.records, start=2):
            output.append({**record, "_row_number": index})
        return output

    def _update_values(self, range_name, rows):
        assert VAULT_TAB in range_name
        row_number = int(range_name.split("A")[-1].split(":")[0])
        self.records[row_number - 2] = dict(zip(VAULT_HEADERS, rows[0]))

    def _append_values(self, range_name, rows):
        if VAULT_TAB in range_name:
            self.records.append(dict(zip(VAULT_HEADERS, rows[0])))
        elif HISTORY_TAB in range_name:
            self.history.append(dict(zip(HISTORY_HEADERS, rows[0])))
        else:
            raise AssertionError(range_name)


BASE_STATE = {
    "address": "1115 Matson Dr, Marion, VA 24354",
    "city": "Marion",
    "state": "VA",
    "zip": "24354",
    "decision_property_input": "1115 Matson Dr, Marion, VA 24354",
    "decision_current_negotiated_price": 25000,
    "decision_result": {
        "decision": "BUY",
        "strategy": "Slow Flip — Keep",
        "first_offer": 28000,
        "hard_max": 32000,
    },
    "rent": 1040,
    "rentcast_rent_comp_count": 4,
    "arv": 35667,
    "arv_confidence": "Strong",
    "rentcast_value_comp_count": 10,
    "repairs": 63476,
}

vault = MemoryVault()
summary = summary_from_state(BASE_STATE)
snapshot = build_snapshot(BASE_STATE)
created = vault.save_deal(
    summary,
    snapshot,
    assigned_to="Carlos",
    stage="Offer Ready",
    priority="High",
    saved_by="Shawn",
)
assert created["action"] == "Created"
assert len(vault.records) == 1
assert len(vault.history) == 1
assert vault.records[0]["assigned_to"] == "Carlos"
assert vault.records[0]["stage"] == "Offer Ready"
assert vault.records[0]["snapshot_payload"].startswith("z1:")
assert vault.history[0]["action"] == "Created"

loaded = vault.load_snapshot(vault.records[0])
assert loaded["saved_state"]["rent"] == 1040
assert loaded["saved_state"]["decision_result"]["decision"] == "BUY"

UPDATED_STATE = dict(BASE_STATE)
UPDATED_STATE["decision_current_negotiated_price"] = 27000
UPDATED_STATE["decision_negotiation_status"] = "Negotiating"
updated = vault.save_deal(
    summary_from_state(UPDATED_STATE),
    build_snapshot(UPDATED_STATE),
    assigned_to="Carlos",
    stage="Negotiating",
    priority="Urgent",
    saved_by="Sabrina",
)
assert updated["action"] == "Updated"
assert len(vault.records) == 1
assert len(vault.history) == 2
assert vault.records[0]["negotiated_price"] == 27000
assert vault.records[0]["stage"] == "Negotiating"
assert vault.records[0]["last_saved_by"] == "Sabrina"
assert "decision_current_negotiated_price" in updated["changed_fields"]
assert vault.history[-1]["action"] == "Updated"

found = vault.find("1115 Matson Dr", records=vault.list_deals())
assert found is not None
assert found["deal_id"] == summary["deal_id"]

print("Deal Vault create, upsert, load, duplicate lookup, and history smoke test passed.")
